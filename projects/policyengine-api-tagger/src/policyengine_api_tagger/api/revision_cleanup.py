"""
Cleanup module for managing Cloud Run traffic tags.

This module provides functionality to:
1. List all existing traffic tags from Cloud Run
2. Determine which tags to keep (newest US, newest UK, plus N most recent)
3. Update the traffic configuration in one atomic operation

Metadata files are NOT touched - they enable on-demand tag recreation.
The manifest is NOT touched - it's kept for historical record.
"""

import re
import logging
from pydantic import BaseModel
from google.cloud.run_v2 import (
    ServicesAsyncClient,
    Service,
    UpdateServiceRequest,
    TrafficTarget,
    TrafficTargetAllocationType,
)

log = logging.getLogger(__name__)


class TagInfo(BaseModel):
    """Information about a traffic tag."""

    tag: str
    revision: str
    country: str  # "us" or "uk"
    version: tuple[int, ...]  # Parsed version for comparison, e.g., (1, 459, 0)
    version_str: str  # Original version string, e.g., "1.459.0"


class CleanupResult(BaseModel):
    """Result of a cleanup operation."""

    total_tags_found: int
    tags_kept: list[str]
    tags_removed: list[str]
    newest_us_tag: str | None
    newest_uk_tag: str | None
    errors: list[str]


class RevisionCleanup:
    def __init__(
        self,
        project_id: str,
        region: str,
        simulation_service_name: str | None = None,
        bucket_name: str | None = None,
        # Alternative shorter parameter names for CLI use
        project: str | None = None,
        service: str | None = None,
    ):
        """
        Initialize RevisionCleanup.

        Args:
            project_id: GCP project ID (or use 'project' shorthand)
            region: GCP region
            simulation_service_name: Name of the simulation API Cloud Run service (or use 'service' shorthand)
            bucket_name: GCS bucket containing metadata files (not used in tag cleanup)
            project: Shorthand for project_id
            service: Shorthand for simulation_service_name
        """
        self.project_id = project or project_id
        self.region = region
        self.simulation_service_name = service or simulation_service_name
        self.bucket_name = bucket_name

    def _get_service_name(self) -> str:
        """Get the full service name for Cloud Run API."""
        return f"projects/{self.project_id}/locations/{self.region}/services/{self.simulation_service_name}"

    def _parse_tag(self, tag: str, revision: str) -> TagInfo | None:
        """
        Parse a tag string to extract country and version.

        Expected format: country-{country}-model-{version with dashes}
        Example: country-us-model-1-459-0 -> country=us, version=(1, 459, 0)
        """
        # Match pattern: country-{us|uk}-model-{version}
        match = re.match(r"^country-(us|uk)-model-(.+)$", tag)
        if not match:
            log.debug(f"Tag '{tag}' doesn't match expected pattern, skipping")
            return None

        country = match.group(1)
        version_with_dashes = match.group(2)

        # Convert dashes back to dots for the version string
        version_str = version_with_dashes.replace("-", ".")

        # Parse version into tuple of integers for comparison
        try:
            version_parts = tuple(int(p) for p in version_str.split("."))
        except ValueError:
            log.warning(f"Could not parse version from tag '{tag}': {version_str}")
            return None

        return TagInfo(
            tag=tag,
            revision=revision,
            country=country,
            version=version_parts,
            version_str=version_str,
        )

    async def _get_service(self) -> Service:
        """Get the Cloud Run service."""
        client = ServicesAsyncClient()
        service_name = self._get_service_name()
        return await client.get_service(name=service_name)

    async def _update_service_traffic(
        self, service: Service, tags_to_keep: list[TagInfo]
    ) -> None:
        """
        Update the service traffic configuration to only include specified tags.

        This rebuilds the traffic list with:
        1. All traffic entries with percent > 0 (main traffic routes)
        2. Only the specified tags (with percent=0)
        """
        client = ServicesAsyncClient()

        # Build new traffic list
        new_traffic = []

        # Keep all traffic with percent > 0 (main traffic routes)
        for entry in service.traffic:
            if entry.percent > 0:
                new_traffic.append(entry)

        # Add the tags we want to keep (with percent=0)
        for tag_info in tags_to_keep:
            new_traffic.append(
                TrafficTarget(
                    type_=TrafficTargetAllocationType.TRAFFIC_TARGET_ALLOCATION_TYPE_REVISION,
                    percent=0,
                    revision=tag_info.revision,
                    tag=tag_info.tag,
                )
            )

        # Update the service
        service.traffic = new_traffic

        request = UpdateServiceRequest(service=service)
        await client.update_service(request=request)

    async def _analyze_tags(
        self, keep_count: int
    ) -> tuple[
        Service | None,
        list[TagInfo],
        list[TagInfo],
        TagInfo | None,
        TagInfo | None,
        list[str],
        list[str],
    ]:
        """
        Analyze tags and determine which to keep/remove.

        Returns:
            Tuple of (service, all_tags, tags_to_keep, newest_us, newest_uk, tags_removed, errors)
        """
        errors: list[str] = []

        # Ensure keep_count is at least 2 (for US + UK safeguards)
        if keep_count < 2:
            keep_count = 2

        # 1. Get the service and its traffic configuration
        try:
            service = await self._get_service()
        except Exception as e:
            log.error(f"Failed to get service: {e}")
            return None, [], [], None, None, [], [f"Failed to get service: {e}"]

        # 2. Parse all existing tags
        all_tags: list[TagInfo] = []
        for entry in service.traffic:
            if entry.tag and entry.percent == 0:
                tag_info = self._parse_tag(entry.tag, entry.revision)
                if tag_info:
                    all_tags.append(tag_info)

        log.info(f"Found {len(all_tags)} traffic tags")

        if not all_tags:
            return service, [], [], None, None, [], []

        # 3. Find newest US and UK tags (safeguards)
        us_tags = [t for t in all_tags if t.country == "us"]
        uk_tags = [t for t in all_tags if t.country == "uk"]

        newest_us = max(us_tags, key=lambda t: t.version) if us_tags else None
        newest_uk = max(uk_tags, key=lambda t: t.version) if uk_tags else None

        log.info(f"Newest US tag: {newest_us.tag if newest_us else 'None'}")
        log.info(f"Newest UK tag: {newest_uk.tag if newest_uk else 'None'}")

        # 4. Build the list of tags to keep
        tags_to_keep: list[TagInfo] = []
        tags_to_keep_set: set[str] = set()

        # Always add newest US and UK first (safeguards)
        if newest_us:
            tags_to_keep.append(newest_us)
            tags_to_keep_set.add(newest_us.tag)

        if newest_uk and newest_uk.tag not in tags_to_keep_set:
            tags_to_keep.append(newest_uk)
            tags_to_keep_set.add(newest_uk.tag)

        # 5. If keep_count > 2, add more tags (sorted by version, newest first)
        remaining_slots = keep_count - len(tags_to_keep)

        if remaining_slots > 0:
            # Sort all tags by version (newest first), combining US and UK
            all_tags_sorted = sorted(all_tags, key=lambda t: t.version, reverse=True)

            for tag_info in all_tags_sorted:
                if remaining_slots <= 0:
                    break
                if tag_info.tag not in tags_to_keep_set:
                    tags_to_keep.append(tag_info)
                    tags_to_keep_set.add(tag_info.tag)
                    remaining_slots -= 1

        # 6. Determine which tags are being removed
        tags_removed = [t.tag for t in all_tags if t.tag not in tags_to_keep_set]

        log.info(f"Keeping {len(tags_to_keep)} tags, removing {len(tags_removed)} tags")

        return (
            service,
            all_tags,
            tags_to_keep,
            newest_us,
            newest_uk,
            tags_removed,
            errors,
        )

    async def preview(self, keep_count: int = 40) -> CleanupResult:
        """
        Preview what cleanup would do without making changes.

        Args:
            keep_count: Number of tags to keep (minimum 2 for US + UK safeguards)

        Returns:
            CleanupResult showing what would be kept/removed
        """
        (
            service,
            all_tags,
            tags_to_keep,
            newest_us,
            newest_uk,
            tags_removed,
            errors,
        ) = await self._analyze_tags(keep_count)

        if service is None:
            return CleanupResult(
                total_tags_found=0,
                tags_kept=[],
                tags_removed=[],
                newest_us_tag=None,
                newest_uk_tag=None,
                errors=errors,
            )

        return CleanupResult(
            total_tags_found=len(all_tags),
            tags_kept=[t.tag for t in tags_to_keep],
            tags_removed=tags_removed,
            newest_us_tag=newest_us.tag if newest_us else None,
            newest_uk_tag=newest_uk.tag if newest_uk else None,
            errors=errors,
        )

    async def cleanup(self, keep_count: int = 40) -> CleanupResult:
        """
        Clean up old traffic tags, keeping the specified number.

        This:
        1. Gets all existing traffic tags from Cloud Run
        2. Identifies the newest US and UK tags (always kept as safeguards)
        3. Keeps the top `keep_count` tags total (including safeguards)
        4. Updates the traffic configuration in one atomic operation

        Args:
            keep_count: Number of tags to keep (minimum 2 for US + UK safeguards)

        Returns:
            CleanupResult with details of what was cleaned up
        """
        (
            service,
            all_tags,
            tags_to_keep,
            newest_us,
            newest_uk,
            tags_removed,
            errors,
        ) = await self._analyze_tags(keep_count)

        if service is None:
            return CleanupResult(
                total_tags_found=0,
                tags_kept=[],
                tags_removed=[],
                newest_us_tag=None,
                newest_uk_tag=None,
                errors=errors,
            )

        if not all_tags:
            return CleanupResult(
                total_tags_found=0,
                tags_kept=[],
                tags_removed=[],
                newest_us_tag=None,
                newest_uk_tag=None,
                errors=[],
            )

        # If there are tags to remove, update the service in one operation
        if tags_removed:
            try:
                await self._update_service_traffic(service, tags_to_keep)
                log.info("Successfully updated traffic configuration")
            except Exception as e:
                log.error(f"Failed to update service traffic: {e}")
                errors.append(f"Failed to update service traffic: {e}")
                # Return without changes since update failed
                return CleanupResult(
                    total_tags_found=len(all_tags),
                    tags_kept=[t.tag for t in all_tags],  # Nothing was removed
                    tags_removed=[],
                    newest_us_tag=newest_us.tag if newest_us else None,
                    newest_uk_tag=newest_uk.tag if newest_uk else None,
                    errors=errors,
                )

        return CleanupResult(
            total_tags_found=len(all_tags),
            tags_kept=[t.tag for t in tags_to_keep],
            tags_removed=tags_removed,
            newest_us_tag=newest_us.tag if newest_us else None,
            newest_uk_tag=newest_uk.tag if newest_uk else None,
            errors=errors,
        )
