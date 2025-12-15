"""Unit tests for revision_cleanup module."""

from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timedelta
import json
import pytest

from google.cloud.run_v2 import (
    TrafficTarget,
    Service,
    TrafficTargetAllocationType,
)

from policyengine_api_tagger.api.revision_cleanup import (
    RevisionCleanup,
    DeploymentEntry,
    CleanupResult,
    _read_manifest_sync,
    _write_manifest_sync,
)


# -----------------------------------------------------------------------------
# Test Fixtures
# -----------------------------------------------------------------------------


@pytest.fixture
def cleanup():
    """Create a RevisionCleanup instance for testing."""
    return RevisionCleanup(
        bucket_name="test-bucket",
        simulation_service_name="api-simulation",
        project_id="test-project",
        region="us-central1",
    )


@pytest.fixture
def sample_manifest():
    """Create a sample manifest with 10 deployments."""
    now = datetime.now()
    return [
        DeploymentEntry(
            revision=f"projects/test-project/locations/us-central1/services/api-simulation/revisions/rev-{i}",
            us=f"1.{i}.0",
            uk=f"2.{i}.0",
            deployed_at=now - timedelta(days=i),
        )
        for i in range(10)
    ]


# -----------------------------------------------------------------------------
# Tests for _compare_versions
# -----------------------------------------------------------------------------


class TestCompareVersions:
    def test_equal_versions(self, cleanup):
        assert cleanup._compare_versions("1.2.3", "1.2.3") == 0

    def test_greater_major_version(self, cleanup):
        assert cleanup._compare_versions("2.0.0", "1.9.9") > 0

    def test_greater_minor_version(self, cleanup):
        assert cleanup._compare_versions("1.3.0", "1.2.9") > 0

    def test_greater_patch_version(self, cleanup):
        assert cleanup._compare_versions("1.2.4", "1.2.3") > 0

    def test_lesser_version(self, cleanup):
        assert cleanup._compare_versions("1.2.3", "1.2.4") < 0

    def test_different_length_versions(self, cleanup):
        assert cleanup._compare_versions("1.2.3.4", "1.2.3") > 0
        assert cleanup._compare_versions("1.2", "1.2.0") == 0

    def test_invalid_version_falls_back_to_string_comparison(self, cleanup):
        # Invalid versions fall back to string comparison
        assert cleanup._compare_versions("abc", "abd") < 0
        assert cleanup._compare_versions("abc", "abc") == 0


# -----------------------------------------------------------------------------
# Tests for _extract_revision_name
# -----------------------------------------------------------------------------


class TestExtractRevisionName:
    def test_extracts_name_from_full_path(self, cleanup):
        full_path = "projects/proj/locations/us/services/svc/revisions/rev-abc123"
        assert cleanup._extract_revision_name(full_path) == "rev-abc123"

    def test_returns_name_as_is_if_no_slashes(self, cleanup):
        name = "rev-abc123"
        assert cleanup._extract_revision_name(name) == "rev-abc123"


# -----------------------------------------------------------------------------
# Tests for _revision_in_keep_set
# -----------------------------------------------------------------------------


class TestRevisionInKeepSet:
    def test_matches_full_path_against_full_path(self, cleanup):
        keep_set = {
            "projects/proj/locations/us/services/svc/revisions/rev-abc"
        }
        assert cleanup._revision_in_keep_set(
            "projects/proj/locations/us/services/svc/revisions/rev-abc",
            keep_set,
        )

    def test_matches_name_against_full_path(self, cleanup):
        keep_set = {
            "projects/proj/locations/us/services/svc/revisions/rev-abc"
        }
        assert cleanup._revision_in_keep_set("rev-abc", keep_set)

    def test_matches_full_path_against_name(self, cleanup):
        keep_set = {"rev-abc"}
        assert cleanup._revision_in_keep_set(
            "projects/proj/locations/us/services/svc/revisions/rev-abc",
            keep_set,
        )

    def test_no_match_returns_false(self, cleanup):
        keep_set = {"rev-abc"}
        assert not cleanup._revision_in_keep_set("rev-xyz", keep_set)


# -----------------------------------------------------------------------------
# Tests for _determine_revisions_to_keep
# -----------------------------------------------------------------------------


class TestDetermineRevisionsToKeep:
    def test_keeps_last_n_deployments(self, cleanup, sample_manifest):
        result = cleanup._determine_revisions_to_keep(sample_manifest, keep_count=5)

        # Should keep rev-0 through rev-4 (5 most recent by deployed_at)
        for i in range(5):
            rev_path = f"projects/test-project/locations/us-central1/services/api-simulation/revisions/rev-{i}"
            assert rev_path in result, f"Expected rev-{i} to be kept"

        # Should not keep rev-5 through rev-9
        for i in range(5, 10):
            rev_path = f"projects/test-project/locations/us-central1/services/api-simulation/revisions/rev-{i}"
            assert rev_path not in result, f"Expected rev-{i} to not be kept"

    def test_empty_manifest_returns_empty_set(self, cleanup):
        result = cleanup._determine_revisions_to_keep([], keep_count=5)
        assert result == set()

    def test_fewer_deployments_than_keep_count(self, cleanup):
        manifest = [
            DeploymentEntry(
                revision="rev-0",
                us="1.0.0",
                uk="2.0.0",
                deployed_at=datetime.now(),
            ),
            DeploymentEntry(
                revision="rev-1",
                us="1.1.0",
                uk="2.1.0",
                deployed_at=datetime.now() - timedelta(days=1),
            ),
        ]
        result = cleanup._determine_revisions_to_keep(manifest, keep_count=5)

        assert "rev-0" in result
        assert "rev-1" in result
        assert len(result) == 2

    def test_safeguard_keeps_highest_us_version(self, cleanup):
        """Even if not in last N, the highest US version should be kept."""
        now = datetime.now()
        manifest = [
            # Most recent deployment with lower US version
            DeploymentEntry(
                revision="rev-recent",
                us="1.0.0",
                uk="2.0.0",
                deployed_at=now,
            ),
            # Old deployment with highest US version
            DeploymentEntry(
                revision="rev-old-high-us",
                us="99.0.0",
                uk="2.0.0",
                deployed_at=now - timedelta(days=100),
            ),
        ]

        result = cleanup._determine_revisions_to_keep(manifest, keep_count=1)

        # Both should be kept: recent (in top 1) and old (safeguard)
        assert "rev-recent" in result
        assert "rev-old-high-us" in result

    def test_safeguard_keeps_highest_uk_version(self, cleanup):
        """Even if not in last N, the highest UK version should be kept."""
        now = datetime.now()
        manifest = [
            # Most recent deployment with lower UK version
            DeploymentEntry(
                revision="rev-recent",
                us="1.0.0",
                uk="2.0.0",
                deployed_at=now,
            ),
            # Old deployment with highest UK version
            DeploymentEntry(
                revision="rev-old-high-uk",
                us="1.0.0",
                uk="99.0.0",
                deployed_at=now - timedelta(days=100),
            ),
        ]

        result = cleanup._determine_revisions_to_keep(manifest, keep_count=1)

        # Both should be kept: recent (in top 1) and old (safeguard)
        assert "rev-recent" in result
        assert "rev-old-high-uk" in result

    def test_safeguard_keeps_both_highest_us_and_uk(self, cleanup):
        """If highest US and UK are on different revisions, keep both."""
        now = datetime.now()
        manifest = [
            DeploymentEntry(
                revision="rev-recent",
                us="1.0.0",
                uk="1.0.0",
                deployed_at=now,
            ),
            DeploymentEntry(
                revision="rev-high-us",
                us="99.0.0",
                uk="1.0.0",
                deployed_at=now - timedelta(days=100),
            ),
            DeploymentEntry(
                revision="rev-high-uk",
                us="1.0.0",
                uk="99.0.0",
                deployed_at=now - timedelta(days=101),
            ),
        ]

        result = cleanup._determine_revisions_to_keep(manifest, keep_count=1)

        assert "rev-recent" in result
        assert "rev-high-us" in result
        assert "rev-high-uk" in result
        assert len(result) == 3

    def test_same_revision_has_highest_us_and_uk(self, cleanup):
        """If same revision has both highest US and UK, it's not duplicated."""
        now = datetime.now()
        manifest = [
            DeploymentEntry(
                revision="rev-recent",
                us="99.0.0",
                uk="99.0.0",
                deployed_at=now,
            ),
            DeploymentEntry(
                revision="rev-old",
                us="1.0.0",
                uk="1.0.0",
                deployed_at=now - timedelta(days=100),
            ),
        ]

        result = cleanup._determine_revisions_to_keep(manifest, keep_count=1)

        assert "rev-recent" in result
        assert len(result) == 1  # Only rev-recent, not duplicated


# -----------------------------------------------------------------------------
# Tests for _remove_old_tags
# -----------------------------------------------------------------------------


class TestRemoveOldTags:
    @pytest.mark.asyncio
    @patch("policyengine_api_tagger.api.revision_cleanup.ServicesAsyncClient")
    async def test_removes_tags_for_old_revisions(self, MockClient, cleanup):
        mock_client = AsyncMock()
        MockClient.return_value = mock_client

        service = Service()
        service.uri = "https://api-simulation.run.app"
        service.traffic = [
            # Main traffic (100%) - should be kept
            TrafficTarget(percent=100, revision="rev-latest"),
            # Tagged revision in keep set - should be kept
            TrafficTarget(
                percent=0, revision="rev-keep", tag="country-us-model-1-0-0"
            ),
            # Tagged revision NOT in keep set - should be removed
            TrafficTarget(
                percent=0, revision="rev-old", tag="country-us-model-0-9-0"
            ),
        ]
        mock_client.get_service.return_value = service

        revisions_to_keep = {"rev-latest", "rev-keep"}
        tags_removed = await cleanup._remove_old_tags(revisions_to_keep)

        assert tags_removed == ["country-us-model-0-9-0"]
        mock_client.update_service.assert_called_once()

        # Verify the updated traffic only has the kept entries
        call_args = mock_client.update_service.call_args
        updated_service = call_args[0][0].service
        assert len(updated_service.traffic) == 2

    @pytest.mark.asyncio
    @patch("policyengine_api_tagger.api.revision_cleanup.ServicesAsyncClient")
    async def test_keeps_traffic_with_nonzero_percent(self, MockClient, cleanup):
        """Traffic with percent > 0 should always be kept."""
        mock_client = AsyncMock()
        MockClient.return_value = mock_client

        service = Service()
        service.uri = "https://api-simulation.run.app"
        service.traffic = [
            # Main traffic (100%) - should be kept even if revision not in keep set
            TrafficTarget(percent=100, revision="rev-not-in-keep-set"),
            # Canary deployment (10%) - should be kept
            TrafficTarget(percent=10, revision="rev-canary"),
        ]
        mock_client.get_service.return_value = service

        revisions_to_keep = {"rev-other"}  # Neither revision in keep set
        tags_removed = await cleanup._remove_old_tags(revisions_to_keep)

        assert tags_removed == []
        mock_client.update_service.assert_not_called()

    @pytest.mark.asyncio
    @patch("policyengine_api_tagger.api.revision_cleanup.ServicesAsyncClient")
    async def test_no_tags_to_remove(self, MockClient, cleanup):
        mock_client = AsyncMock()
        MockClient.return_value = mock_client

        service = Service()
        service.uri = "https://api-simulation.run.app"
        service.traffic = [
            TrafficTarget(percent=100, revision="rev-latest"),
            TrafficTarget(
                percent=0, revision="rev-keep", tag="country-us-model-1-0-0"
            ),
        ]
        mock_client.get_service.return_value = service

        revisions_to_keep = {"rev-latest", "rev-keep"}
        tags_removed = await cleanup._remove_old_tags(revisions_to_keep)

        assert tags_removed == []
        mock_client.update_service.assert_not_called()


# -----------------------------------------------------------------------------
# Tests for _cleanup_metadata_files
# -----------------------------------------------------------------------------


class TestCleanupMetadataFiles:
    @pytest.mark.asyncio
    async def test_deletes_metadata_for_old_revisions(self, cleanup):
        with patch.object(
            cleanup, "_list_metadata_files", new_callable=AsyncMock
        ) as mock_list, patch.object(
            cleanup, "_read_metadata_file", new_callable=AsyncMock
        ) as mock_read, patch.object(
            cleanup, "_delete_metadata_file", new_callable=AsyncMock
        ) as mock_delete:
            mock_list.return_value = [
                "us.1.0.0.json",  # Keep
                "us.0.9.0.json",  # Delete
                "uk.2.0.0.json",  # Keep
                "live.json",  # Skip (special file)
                "deployments.json",  # Skip (special file)
            ]

            def read_side_effect(filename):
                if filename == "us.1.0.0.json":
                    return {"revision": "rev-keep"}
                elif filename == "us.0.9.0.json":
                    return {"revision": "rev-old"}
                elif filename == "uk.2.0.0.json":
                    return {"revision": "rev-keep"}
                return None

            mock_read.side_effect = read_side_effect

            revisions_to_keep = {"rev-keep"}
            deleted = await cleanup._cleanup_metadata_files(revisions_to_keep)

            assert deleted == ["us.0.9.0.json"]
            mock_delete.assert_called_once_with("us.0.9.0.json")

    @pytest.mark.asyncio
    async def test_skips_special_files(self, cleanup):
        with patch.object(
            cleanup, "_list_metadata_files", new_callable=AsyncMock
        ) as mock_list, patch.object(
            cleanup, "_read_metadata_file", new_callable=AsyncMock
        ) as mock_read, patch.object(
            cleanup, "_delete_metadata_file", new_callable=AsyncMock
        ) as mock_delete:
            mock_list.return_value = [
                "live.json",
                "deployments.json",
            ]

            deleted = await cleanup._cleanup_metadata_files({"rev-keep"})

            assert deleted == []
            mock_read.assert_not_called()
            mock_delete.assert_not_called()


# -----------------------------------------------------------------------------
# Tests for cleanup (full flow)
# -----------------------------------------------------------------------------


class TestCleanup:
    @pytest.mark.asyncio
    async def test_full_cleanup_flow(self, cleanup, sample_manifest):
        with patch.object(
            cleanup, "_read_manifest", new_callable=AsyncMock
        ) as mock_read_manifest, patch.object(
            cleanup, "_remove_old_tags", new_callable=AsyncMock
        ) as mock_remove_tags, patch.object(
            cleanup, "_cleanup_metadata_files", new_callable=AsyncMock
        ) as mock_cleanup_files, patch.object(
            cleanup, "_write_manifest", new_callable=AsyncMock
        ) as mock_write_manifest:
            mock_read_manifest.return_value = sample_manifest[:6]  # 6 deployments
            mock_remove_tags.return_value = ["tag-1", "tag-2"]
            mock_cleanup_files.return_value = ["us.old.json"]

            result = await cleanup.cleanup(keep_count=5)

            assert len(result.revisions_kept) == 5
            assert result.tags_removed == ["tag-1", "tag-2"]
            assert result.metadata_files_deleted == ["us.old.json"]
            assert result.errors == []

            # Verify manifest was written with only kept revisions
            mock_write_manifest.assert_called_once()

    @pytest.mark.asyncio
    async def test_cleanup_with_no_manifest(self, cleanup):
        with patch.object(
            cleanup, "_read_manifest", new_callable=AsyncMock
        ) as mock_read_manifest:
            mock_read_manifest.return_value = []

            result = await cleanup.cleanup(keep_count=5)

            assert result.revisions_kept == []
            assert result.tags_removed == []
            assert result.metadata_files_deleted == []
            assert "No deployment manifest found" in result.errors

    @pytest.mark.asyncio
    async def test_cleanup_handles_errors_gracefully(self, cleanup, sample_manifest):
        with patch.object(
            cleanup, "_read_manifest", new_callable=AsyncMock
        ) as mock_read_manifest, patch.object(
            cleanup, "_remove_old_tags", new_callable=AsyncMock
        ) as mock_remove_tags, patch.object(
            cleanup, "_cleanup_metadata_files", new_callable=AsyncMock
        ) as mock_cleanup_files, patch.object(
            cleanup, "_write_manifest", new_callable=AsyncMock
        ) as mock_write_manifest:
            mock_read_manifest.return_value = sample_manifest[:3]
            mock_remove_tags.side_effect = Exception("Cloud Run API error")
            mock_cleanup_files.return_value = []

            result = await cleanup.cleanup(keep_count=5)

            # Should continue despite error
            assert len(result.revisions_kept) > 0
            assert "Failed to remove tags" in result.errors[0]
            mock_cleanup_files.assert_called_once()  # Should still attempt cleanup


# -----------------------------------------------------------------------------
# Tests for manifest read/write functions
# -----------------------------------------------------------------------------


class TestManifestReadWrite:
    def test_read_manifest_returns_empty_on_missing_file(self):
        with patch(
            "policyengine_api_tagger.api.revision_cleanup.storage.Client"
        ) as MockClient:
            mock_client = MagicMock()
            MockClient.return_value = mock_client
            mock_bucket = MagicMock()
            mock_client.bucket.return_value = mock_bucket
            mock_blob = MagicMock()
            mock_bucket.blob.return_value = mock_blob
            mock_blob.exists.return_value = False

            result = _read_manifest_sync("test-bucket")

            assert result == []

    def test_read_manifest_parses_json(self):
        with patch(
            "policyengine_api_tagger.api.revision_cleanup.storage.Client"
        ) as MockClient:
            mock_client = MagicMock()
            MockClient.return_value = mock_client
            mock_bucket = MagicMock()
            mock_client.bucket.return_value = mock_bucket
            mock_blob = MagicMock()
            mock_bucket.blob.return_value = mock_blob
            mock_blob.exists.return_value = True
            mock_blob.download_as_text.return_value = json.dumps(
                [
                    {
                        "revision": "rev-1",
                        "us": "1.0.0",
                        "uk": "2.0.0",
                        "deployed_at": "2025-01-01T00:00:00Z",
                    }
                ]
            )

            result = _read_manifest_sync("test-bucket")

            assert len(result) == 1
            assert result[0].revision == "rev-1"
            assert result[0].us == "1.0.0"

    def test_write_manifest_uses_atomic_pattern(self):
        with patch(
            "policyengine_api_tagger.api.revision_cleanup.storage.Client"
        ) as MockClient:
            mock_client = MagicMock()
            MockClient.return_value = mock_client
            mock_bucket = MagicMock()
            mock_client.bucket.return_value = mock_bucket
            mock_temp_blob = MagicMock()
            mock_bucket.blob.return_value = mock_temp_blob

            entries = [
                DeploymentEntry(
                    revision="rev-1",
                    us="1.0.0",
                    uk="2.0.0",
                    deployed_at=datetime.now(),
                )
            ]

            _write_manifest_sync("test-bucket", entries)

            # Should write to temp, then copy
            mock_temp_blob.upload_from_string.assert_called_once()
            mock_bucket.copy_blob.assert_called_once()
            # Should clean up temp
            mock_temp_blob.delete.assert_called_once()
