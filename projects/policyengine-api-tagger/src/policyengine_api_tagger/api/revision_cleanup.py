"""
Cleanup module for removing old Cloud Run revisions and their associated tags.

This module provides functionality to:
1. Read the deployment manifest from GCS
2. Determine which revisions should be kept (last N deployments + safeguards)
3. Remove Cloud Run traffic tags for old revisions
4. Delete old metadata files from GCS
"""

from google.cloud import storage
from google.cloud.run_v2 import (
    ServicesAsyncClient,
    RevisionsAsyncClient,
    UpdateServiceRequest,
    GetServiceRequest,
    DeleteRevisionRequest,
)
from pydantic import BaseModel
from anyio import to_thread
import logging
from datetime import datetime

log = logging.getLogger(__name__)


class DeploymentEntry(BaseModel):
    """A single entry in the deployments manifest."""

    revision: str
    us: str
    uk: str
    deployed_at: datetime


class CleanupResult(BaseModel):
    """Result of a cleanup operation."""

    revisions_kept: list[str]
    revisions_removed: list[str]
    tags_removed: list[str]
    metadata_files_deleted: list[str]
    errors: list[str]


def _read_manifest_sync(bucket_name: str) -> list[DeploymentEntry]:
    """Read the deployments manifest from GCS."""
    storage_client = storage.Client()
    blob = storage_client.bucket(bucket_name).blob("deployments.json")

    if not blob.exists():
        log.info("No deployments.json manifest found, returning empty list")
        return []

    import json

    content = blob.download_as_text()
    data = json.loads(content)
    return [DeploymentEntry.model_validate(entry) for entry in data]


def _write_manifest_sync(bucket_name: str, entries: list[DeploymentEntry]) -> None:
    """Write the deployments manifest to GCS."""
    import json

    storage_client = storage.Client()
    blob = storage_client.bucket(bucket_name).blob("deployments.json")

    data = [entry.model_dump(mode="json") for entry in entries]
    blob.upload_from_string(json.dumps(data, indent=2, default=str))
    log.info(f"Updated manifest with {len(entries)} entries")


def _list_metadata_files_sync(bucket_name: str) -> list[str]:
    """List all country version metadata files in the bucket."""
    storage_client = storage.Client()
    bucket = storage_client.bucket(bucket_name)

    files = []
    for blob in bucket.list_blobs():
        name = blob.name
        # Match patterns like us.1.2.3.json or uk.2.0.0.json
        if (name.startswith("us.") or name.startswith("uk.")) and name.endswith(
            ".json"
        ):
            files.append(name)
    return files


def _delete_blob_sync(bucket_name: str, blob_name: str) -> None:
    """Delete a blob from GCS."""
    storage_client = storage.Client()
    blob = storage_client.bucket(bucket_name).blob(blob_name)
    blob.delete()
    log.info(f"Deleted metadata file: {blob_name}")


def _read_metadata_file_sync(bucket_name: str, blob_name: str) -> dict | None:
    """Read a metadata file and return its contents."""
    import json

    storage_client = storage.Client()
    blob = storage_client.bucket(bucket_name).blob(blob_name)

    if not blob.exists():
        return None

    content = blob.download_as_text()
    return json.loads(content)


class RevisionCleanup:
    def __init__(
        self,
        bucket_name: str,
        simulation_service_name: str,
        project_id: str,
        region: str,
    ):
        """
        Initialize RevisionCleanup.

        Args:
            bucket_name: GCS bucket containing metadata and manifest
            simulation_service_name: Name of the simulation API Cloud Run service
            project_id: GCP project ID
            region: GCP region
        """
        self.bucket_name = bucket_name
        self.simulation_service_name = simulation_service_name
        self.project_id = project_id
        self.region = region

    def _get_full_service_name(self) -> str:
        """Get the full Cloud Run service resource name."""
        return f"projects/{self.project_id}/locations/{self.region}/services/{self.simulation_service_name}"

    async def _read_manifest(self) -> list[DeploymentEntry]:
        """Read the deployment manifest from GCS."""
        return await to_thread.run_sync(_read_manifest_sync, self.bucket_name)

    async def _write_manifest(self, entries: list[DeploymentEntry]) -> None:
        """Write the deployment manifest to GCS."""
        await to_thread.run_sync(_write_manifest_sync, self.bucket_name, entries)

    async def _list_metadata_files(self) -> list[str]:
        """List all metadata files in the bucket."""
        return await to_thread.run_sync(_list_metadata_files_sync, self.bucket_name)

    async def _delete_metadata_file(self, blob_name: str) -> None:
        """Delete a metadata file from GCS."""
        await to_thread.run_sync(_delete_blob_sync, self.bucket_name, blob_name)

    async def _read_metadata_file(self, blob_name: str) -> dict | None:
        """Read a metadata file."""
        return await to_thread.run_sync(
            _read_metadata_file_sync, self.bucket_name, blob_name
        )

    def _determine_revisions_to_keep(
        self, manifest: list[DeploymentEntry], keep_count: int
    ) -> set[str]:
        """
        Determine which revisions should be kept.

        Safeguards:
        1. Keep the last `keep_count` deployments
        2. ALWAYS keep the revision with the most recent US version
        3. ALWAYS keep the revision with the most recent UK version

        This ensures we never delete the latest version of either country package,
        even if there's a bug or unusual deployment pattern.
        """
        if not manifest:
            return set()

        # Sort by deployment time, newest first
        sorted_manifest = sorted(manifest, key=lambda x: x.deployed_at, reverse=True)

        # Start with the last N deployments
        revisions_to_keep = set()
        for entry in sorted_manifest[:keep_count]:
            revisions_to_keep.add(entry.revision)

        # Safeguard: Find and keep the most recent US version
        # (the one deployed most recently that has a US version)
        most_recent_us_revision = None
        most_recent_us_version = None
        for entry in sorted_manifest:
            if entry.us:
                if most_recent_us_version is None or self._compare_versions(
                    entry.us, most_recent_us_version
                ) > 0:
                    most_recent_us_version = entry.us
                    most_recent_us_revision = entry.revision

        if most_recent_us_revision:
            if most_recent_us_revision not in revisions_to_keep:
                log.info(
                    f"Safeguard: Keeping revision {most_recent_us_revision} "
                    f"as it has the most recent US version ({most_recent_us_version})"
                )
            revisions_to_keep.add(most_recent_us_revision)

        # Safeguard: Find and keep the most recent UK version
        most_recent_uk_revision = None
        most_recent_uk_version = None
        for entry in sorted_manifest:
            if entry.uk:
                if most_recent_uk_version is None or self._compare_versions(
                    entry.uk, most_recent_uk_version
                ) > 0:
                    most_recent_uk_version = entry.uk
                    most_recent_uk_revision = entry.revision

        if most_recent_uk_revision:
            if most_recent_uk_revision not in revisions_to_keep:
                log.info(
                    f"Safeguard: Keeping revision {most_recent_uk_revision} "
                    f"as it has the most recent UK version ({most_recent_uk_version})"
                )
            revisions_to_keep.add(most_recent_uk_revision)

        return revisions_to_keep

    def _compare_versions(self, v1: str, v2: str) -> int:
        """
        Compare two semantic versions.
        Returns: positive if v1 > v2, negative if v1 < v2, 0 if equal.
        """
        try:
            parts1 = [int(x) for x in v1.split(".")]
            parts2 = [int(x) for x in v2.split(".")]

            # Pad shorter version with zeros
            max_len = max(len(parts1), len(parts2))
            parts1.extend([0] * (max_len - len(parts1)))
            parts2.extend([0] * (max_len - len(parts2)))

            for p1, p2 in zip(parts1, parts2):
                if p1 > p2:
                    return 1
                if p1 < p2:
                    return -1
            return 0
        except (ValueError, AttributeError):
            # If version parsing fails, fall back to string comparison
            if v1 > v2:
                return 1
            if v1 < v2:
                return -1
            return 0

    def _extract_revision_name(self, revision: str) -> str:
        """Extract just the revision name from a full path or return as-is."""
        if "/" in revision:
            return revision.split("/")[-1]
        return revision

    def _revision_in_keep_set(self, revision: str, revisions_to_keep: set[str]) -> bool:
        """Check if a revision is in the keep set, handling full paths vs names."""
        revision_name = self._extract_revision_name(revision)
        for keep_rev in revisions_to_keep:
            keep_rev_name = self._extract_revision_name(keep_rev)
            if revision_name == keep_rev_name:
                return True
        return False

    async def _remove_old_tags(self, revisions_to_keep: set[str]) -> list[str]:
        """
        Remove Cloud Run traffic tags for revisions not in the keep set.

        Returns list of removed tag names.
        """
        services_client = ServicesAsyncClient()
        service_name = self._get_full_service_name()

        log.info(f"Fetching service {service_name} to check tags")
        service = await services_client.get_service(
            GetServiceRequest(name=service_name)
        )

        # Find tags to remove
        tags_to_remove = []
        traffic_to_keep = []

        for traffic in service.traffic:
            # Always keep traffic entries with percent > 0 (main traffic route)
            if traffic.percent > 0:
                traffic_to_keep.append(traffic)
                continue

            # Check if this traffic entry's revision should be kept
            revision_name = traffic.revision
            if revision_name and self._revision_in_keep_set(
                revision_name, revisions_to_keep
            ):
                traffic_to_keep.append(traffic)
            elif traffic.tag:
                tags_to_remove.append(traffic.tag)
                log.info(
                    f"Marking tag '{traffic.tag}' for removal "
                    f"(revision: {revision_name})"
                )
            else:
                traffic_to_keep.append(traffic)

        if not tags_to_remove:
            log.info("No tags to remove")
            return []

        # Update service with filtered traffic
        service.traffic = traffic_to_keep

        log.info(f"Removing {len(tags_to_remove)} tags from service")
        await services_client.update_service(
            UpdateServiceRequest(service=service, update_mask={"paths": ["traffic"]})
        )

        return tags_to_remove

    async def _delete_old_revisions(
        self, manifest: list[DeploymentEntry], revisions_to_keep: set[str]
    ) -> list[str]:
        """
        Delete Cloud Run revisions not in the keep set.

        Returns list of deleted revision names.
        """
        revisions_client = RevisionsAsyncClient()
        deleted = []

        for entry in manifest:
            if entry.revision not in revisions_to_keep:
                # Extract just the revision name from the full path if needed
                revision_path = entry.revision
                if not revision_path.startswith("projects/"):
                    revision_path = f"projects/{self.project_id}/locations/{self.region}/services/{self.simulation_service_name}/revisions/{entry.revision}"

                try:
                    log.info(f"Deleting revision: {revision_path}")
                    await revisions_client.delete_revision(
                        DeleteRevisionRequest(name=revision_path)
                    )
                    deleted.append(entry.revision)
                except Exception as e:
                    log.warning(f"Failed to delete revision {revision_path}: {e}")

        return deleted

    async def _cleanup_metadata_files(
        self, manifest: list[DeploymentEntry], revisions_to_keep: set[str]
    ) -> list[str]:
        """
        Delete metadata files that point to revisions not in the keep set.

        Returns list of deleted file names.
        """
        metadata_files = await self._list_metadata_files()
        deleted = []

        for file_name in metadata_files:
            # Skip special files
            if file_name in ["live.json", "deployments.json"]:
                continue

            # Read the file to check which revision it points to
            metadata = await self._read_metadata_file(file_name)
            if metadata is None:
                continue

            revision = metadata.get("revision", "")

            # Check if this revision should be kept
            if not self._revision_in_keep_set(revision, revisions_to_keep):
                try:
                    await self._delete_metadata_file(file_name)
                    deleted.append(file_name)
                except Exception as e:
                    log.warning(f"Failed to delete metadata file {file_name}: {e}")

        return deleted

    async def cleanup(
        self, keep_count: int = 5, delete_revisions: bool = False
    ) -> CleanupResult:
        """
        Perform cleanup of old revisions and tags.

        Args:
            keep_count: Number of recent deployments to keep (minimum, safeguards may keep more)
            delete_revisions: If True, also delete old Cloud Run revisions (not just tags)

        Returns:
            CleanupResult with details of what was cleaned up
        """
        errors: list[str] = []

        # 1. Read manifest
        manifest = await self._read_manifest()
        if not manifest:
            log.info("No manifest found, nothing to clean up")
            return CleanupResult(
                revisions_kept=[],
                revisions_removed=[],
                tags_removed=[],
                metadata_files_deleted=[],
                errors=["No deployment manifest found"],
            )

        log.info(f"Found {len(manifest)} deployments in manifest")

        # 2. Determine which revisions to keep (with safeguards)
        revisions_to_keep = self._determine_revisions_to_keep(manifest, keep_count)
        log.info(f"Keeping {len(revisions_to_keep)} revisions")

        # 3. Remove tags for old revisions
        try:
            tags_removed = await self._remove_old_tags(revisions_to_keep)
        except Exception as e:
            log.error(f"Failed to remove old tags: {e}")
            tags_removed = []
            errors.append(f"Failed to remove tags: {e}")

        # 4. Delete old metadata files
        try:
            metadata_deleted = await self._cleanup_metadata_files(
                manifest, revisions_to_keep
            )
        except Exception as e:
            log.error(f"Failed to cleanup metadata files: {e}")
            metadata_deleted = []
            errors.append(f"Failed to cleanup metadata files: {e}")

        # 5. Optionally delete old revisions
        revisions_removed = []
        if delete_revisions:
            try:
                revisions_removed = await self._delete_old_revisions(
                    manifest, revisions_to_keep
                )
            except Exception as e:
                log.error(f"Failed to delete old revisions: {e}")
                errors.append(f"Failed to delete revisions: {e}")

        # 6. Update manifest to only include kept revisions
        updated_manifest = [
            entry for entry in manifest if entry.revision in revisions_to_keep
        ]
        try:
            await self._write_manifest(updated_manifest)
        except Exception as e:
            log.error(f"Failed to update manifest: {e}")
            errors.append(f"Failed to update manifest: {e}")

        return CleanupResult(
            revisions_kept=list(revisions_to_keep),
            revisions_removed=revisions_removed,
            tags_removed=tags_removed,
            metadata_files_deleted=metadata_deleted,
            errors=errors,
        )
