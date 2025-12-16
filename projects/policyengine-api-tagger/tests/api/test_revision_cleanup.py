"""Unit tests for revision_cleanup module."""

from unittest.mock import AsyncMock, MagicMock, patch
import pytest

from policyengine_api_tagger.api.revision_cleanup import (
    RevisionCleanup,
    CleanupResult,
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
# Tests for _list_existing_revisions
# -----------------------------------------------------------------------------


class TestListExistingRevisions:
    @pytest.mark.asyncio
    @patch("policyengine_api_tagger.api.revision_cleanup.RevisionsAsyncClient")
    async def test_lists_revisions_from_cloud_run(self, MockClient, cleanup):
        mock_client = AsyncMock()
        MockClient.return_value = mock_client

        # Create mock revision objects
        mock_rev1 = MagicMock()
        mock_rev1.name = "projects/test-project/locations/us-central1/services/api-simulation/revisions/rev-abc123"
        mock_rev2 = MagicMock()
        mock_rev2.name = "projects/test-project/locations/us-central1/services/api-simulation/revisions/rev-def456"

        # Mock the async iterator
        async def mock_list_revisions(request):
            async def async_gen():
                yield mock_rev1
                yield mock_rev2

            return async_gen()

        mock_client.list_revisions = mock_list_revisions

        result = await cleanup._list_existing_revisions()

        assert result == {"rev-abc123", "rev-def456"}


# -----------------------------------------------------------------------------
# Tests for cleanup (main flow)
# -----------------------------------------------------------------------------


class TestCleanup:
    @pytest.mark.asyncio
    async def test_deletes_metadata_for_nonexistent_revisions(self, cleanup):
        with (
            patch.object(
                cleanup, "_list_existing_revisions", new_callable=AsyncMock
            ) as mock_list_revisions,
            patch.object(
                cleanup, "_list_metadata_files", new_callable=AsyncMock
            ) as mock_list_files,
            patch.object(
                cleanup, "_read_metadata_file", new_callable=AsyncMock
            ) as mock_read,
            patch.object(
                cleanup, "_delete_metadata_file", new_callable=AsyncMock
            ) as mock_delete,
        ):
            # Cloud Run has these revisions
            mock_list_revisions.return_value = {"rev-exists-1", "rev-exists-2"}

            # GCS has these metadata files
            mock_list_files.return_value = [
                "us.1.0.0.json",  # Points to existing revision
                "us.0.9.0.json",  # Points to deleted revision
                "uk.2.0.0.json",  # Points to existing revision
            ]

            def read_side_effect(filename):
                if filename == "us.1.0.0.json":
                    return {"revision": "projects/.../revisions/rev-exists-1"}
                elif filename == "us.0.9.0.json":
                    return {"revision": "projects/.../revisions/rev-deleted"}
                elif filename == "uk.2.0.0.json":
                    return {"revision": "projects/.../revisions/rev-exists-2"}
                return None

            mock_read.side_effect = read_side_effect

            result = await cleanup.cleanup()

            # Should delete metadata file for non-existent revision
            assert result.metadata_files_deleted == ["us.0.9.0.json"]
            mock_delete.assert_called_once_with("us.0.9.0.json")

            # Should report kept files
            assert "us.1.0.0.json" in result.metadata_files_kept
            assert "uk.2.0.0.json" in result.metadata_files_kept

            # Should report existing revisions
            assert set(result.existing_revisions) == {"rev-exists-1", "rev-exists-2"}

    @pytest.mark.asyncio
    async def test_skips_special_files(self, cleanup):
        with (
            patch.object(
                cleanup, "_list_existing_revisions", new_callable=AsyncMock
            ) as mock_list_revisions,
            patch.object(
                cleanup, "_list_metadata_files", new_callable=AsyncMock
            ) as mock_list_files,
            patch.object(
                cleanup, "_read_metadata_file", new_callable=AsyncMock
            ) as mock_read,
            patch.object(
                cleanup, "_delete_metadata_file", new_callable=AsyncMock
            ) as mock_delete,
        ):
            mock_list_revisions.return_value = {"rev-1"}
            mock_list_files.return_value = [
                "live.json",
                "deployments.json",
            ]

            result = await cleanup.cleanup()

            # Special files should be skipped, not read or deleted
            mock_read.assert_not_called()
            mock_delete.assert_not_called()
            assert result.metadata_files_deleted == []
            assert result.metadata_files_kept == []

    @pytest.mark.asyncio
    async def test_handles_missing_revision_field(self, cleanup):
        with (
            patch.object(
                cleanup, "_list_existing_revisions", new_callable=AsyncMock
            ) as mock_list_revisions,
            patch.object(
                cleanup, "_list_metadata_files", new_callable=AsyncMock
            ) as mock_list_files,
            patch.object(
                cleanup, "_read_metadata_file", new_callable=AsyncMock
            ) as mock_read,
            patch.object(
                cleanup, "_delete_metadata_file", new_callable=AsyncMock
            ) as mock_delete,
        ):
            mock_list_revisions.return_value = {"rev-1"}
            mock_list_files.return_value = ["us.1.0.0.json"]
            mock_read.return_value = {"uri": "https://example.com"}  # No revision field

            result = await cleanup.cleanup()

            # Should skip file without revision field
            mock_delete.assert_not_called()
            assert result.metadata_files_deleted == []

    @pytest.mark.asyncio
    async def test_handles_invalid_json_gracefully(self, cleanup):
        with (
            patch.object(
                cleanup, "_list_existing_revisions", new_callable=AsyncMock
            ) as mock_list_revisions,
            patch.object(
                cleanup, "_list_metadata_files", new_callable=AsyncMock
            ) as mock_list_files,
            patch.object(
                cleanup, "_read_metadata_file", new_callable=AsyncMock
            ) as mock_read,
            patch.object(
                cleanup, "_delete_metadata_file", new_callable=AsyncMock
            ) as mock_delete,
        ):
            mock_list_revisions.return_value = {"rev-1"}
            mock_list_files.return_value = ["us.1.0.0.json"]
            mock_read.return_value = None  # Invalid JSON returns None

            result = await cleanup.cleanup()

            # Should skip file with invalid JSON
            mock_delete.assert_not_called()
            assert result.metadata_files_deleted == []
            assert result.errors == []  # No error added, just skipped

    @pytest.mark.asyncio
    async def test_handles_list_revisions_failure(self, cleanup):
        with patch.object(
            cleanup, "_list_existing_revisions", new_callable=AsyncMock
        ) as mock_list_revisions:
            mock_list_revisions.side_effect = Exception("Cloud Run API error")

            result = await cleanup.cleanup()

            assert result.existing_revisions == []
            assert result.metadata_files_deleted == []
            assert result.metadata_files_kept == []
            assert "Failed to list revisions" in result.errors[0]

    @pytest.mark.asyncio
    async def test_handles_list_metadata_files_failure(self, cleanup):
        with (
            patch.object(
                cleanup, "_list_existing_revisions", new_callable=AsyncMock
            ) as mock_list_revisions,
            patch.object(
                cleanup, "_list_metadata_files", new_callable=AsyncMock
            ) as mock_list_files,
        ):
            mock_list_revisions.return_value = {"rev-1", "rev-2"}
            mock_list_files.side_effect = Exception("GCS error")

            result = await cleanup.cleanup()

            assert set(result.existing_revisions) == {"rev-1", "rev-2"}
            assert result.metadata_files_deleted == []
            assert result.metadata_files_kept == []
            assert "Failed to list metadata files" in result.errors[0]

    @pytest.mark.asyncio
    async def test_handles_delete_failure_and_continues(self, cleanup):
        with (
            patch.object(
                cleanup, "_list_existing_revisions", new_callable=AsyncMock
            ) as mock_list_revisions,
            patch.object(
                cleanup, "_list_metadata_files", new_callable=AsyncMock
            ) as mock_list_files,
            patch.object(
                cleanup, "_read_metadata_file", new_callable=AsyncMock
            ) as mock_read,
            patch.object(
                cleanup, "_delete_metadata_file", new_callable=AsyncMock
            ) as mock_delete,
        ):
            mock_list_revisions.return_value = {"rev-1"}
            mock_list_files.return_value = [
                "us.1.0.0.json",  # Delete will fail
                "us.2.0.0.json",  # Delete will succeed
            ]

            def read_side_effect(filename):
                return {"revision": "rev-deleted"}  # All point to deleted revision

            mock_read.side_effect = read_side_effect

            # First delete fails, second succeeds
            mock_delete.side_effect = [Exception("GCS error"), None]

            result = await cleanup.cleanup()

            # Should continue despite first failure
            assert mock_delete.call_count == 2
            assert result.metadata_files_deleted == ["us.2.0.0.json"]
            assert "Failed to delete us.1.0.0.json" in result.errors[0]

    @pytest.mark.asyncio
    async def test_no_cleanup_needed_when_all_revisions_exist(self, cleanup):
        with (
            patch.object(
                cleanup, "_list_existing_revisions", new_callable=AsyncMock
            ) as mock_list_revisions,
            patch.object(
                cleanup, "_list_metadata_files", new_callable=AsyncMock
            ) as mock_list_files,
            patch.object(
                cleanup, "_read_metadata_file", new_callable=AsyncMock
            ) as mock_read,
            patch.object(
                cleanup, "_delete_metadata_file", new_callable=AsyncMock
            ) as mock_delete,
        ):
            mock_list_revisions.return_value = {"rev-1", "rev-2", "rev-3"}
            mock_list_files.return_value = [
                "us.1.0.0.json",
                "us.2.0.0.json",
            ]

            def read_side_effect(filename):
                if filename == "us.1.0.0.json":
                    return {"revision": "rev-1"}
                elif filename == "us.2.0.0.json":
                    return {"revision": "rev-2"}
                return None

            mock_read.side_effect = read_side_effect

            result = await cleanup.cleanup()

            # Nothing should be deleted
            mock_delete.assert_not_called()
            assert result.metadata_files_deleted == []
            assert len(result.metadata_files_kept) == 2
            assert result.errors == []


# -----------------------------------------------------------------------------
# Tests for _read_metadata_file_sync
# -----------------------------------------------------------------------------


class TestReadMetadataFileSync:
    def test_returns_none_for_missing_file(self):
        from policyengine_api_tagger.api.revision_cleanup import (
            _read_metadata_file_sync,
        )

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

            result = _read_metadata_file_sync("test-bucket", "us.1.0.0.json")

            assert result is None

    def test_returns_none_for_invalid_json(self):
        from policyengine_api_tagger.api.revision_cleanup import (
            _read_metadata_file_sync,
        )

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
            mock_blob.download_as_text.return_value = "{invalid json"

            result = _read_metadata_file_sync("test-bucket", "us.1.0.0.json")

            assert result is None

    def test_returns_parsed_json(self):
        from policyengine_api_tagger.api.revision_cleanup import (
            _read_metadata_file_sync,
        )

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
            mock_blob.download_as_text.return_value = '{"revision": "rev-1", "uri": "https://example.com"}'

            result = _read_metadata_file_sync("test-bucket", "us.1.0.0.json")

            assert result == {"revision": "rev-1", "uri": "https://example.com"}
