"""Integration tests for the cleanup endpoint."""

from unittest.mock import AsyncMock, MagicMock, patch
import json
import pytest
from fastapi.testclient import TestClient
from fastapi import FastAPI

from policyengine_api_tagger.api.revision_tagger import RevisionTagger
from policyengine_api_tagger.api.revision_cleanup import RevisionCleanup
from policyengine_api_tagger.api.routes import add_all_routes


# -----------------------------------------------------------------------------
# Local Integration Tests (with mocks)
# -----------------------------------------------------------------------------


class TestCleanupEndpointLocal:
    """Tests the cleanup endpoint with mocked GCS and Cloud Run."""

    @pytest.fixture
    def mock_gcs(self):
        """Mock GCS storage client."""
        with patch(
            "policyengine_api_tagger.api.revision_cleanup.storage.Client"
        ) as MockClient:
            mock_client = MagicMock()
            MockClient.return_value = mock_client
            mock_bucket = MagicMock()
            mock_client.bucket.return_value = mock_bucket

            # Store for tracking what's in the bucket
            bucket_contents = {}

            def mock_blob(name):
                blob = MagicMock()
                blob.name = name

                def exists():
                    return name in bucket_contents

                def download_as_text():
                    return bucket_contents.get(name, "")

                def upload_from_string(content, content_type=None):
                    bucket_contents[name] = content

                def delete():
                    if name in bucket_contents:
                        del bucket_contents[name]

                blob.exists = exists
                blob.download_as_text = download_as_text
                blob.upload_from_string = upload_from_string
                blob.delete = delete
                return blob

            mock_bucket.blob = mock_blob

            def list_blobs():
                return [mock_blob(name) for name in bucket_contents.keys()]

            mock_bucket.list_blobs = list_blobs

            yield {
                "client": mock_client,
                "bucket": mock_bucket,
                "contents": bucket_contents,
            }

    @pytest.fixture
    def mock_cloudrun_revisions(self):
        """Mock Cloud Run revisions client."""
        with patch(
            "policyengine_api_tagger.api.revision_cleanup.RevisionsAsyncClient"
        ) as MockClient:
            mock_client = AsyncMock()
            MockClient.return_value = mock_client

            # Store for existing revisions
            existing_revisions = []

            async def mock_list_revisions(request):
                async def async_gen():
                    for rev_name in existing_revisions:
                        mock_rev = MagicMock()
                        mock_rev.name = f"projects/test-project/locations/us-central1/services/api-simulation/revisions/{rev_name}"
                        yield mock_rev

                return async_gen()

            mock_client.list_revisions = mock_list_revisions

            yield {
                "client": mock_client,
                "revisions": existing_revisions,
            }

    @pytest.fixture
    def client(self, mock_gcs, mock_cloudrun_revisions):
        """Create test client with mocked dependencies."""
        app = FastAPI(
            title="policyengine-api-tagger-test",
            summary="Test instance",
        )

        # Mock the revision tagger's blob access too
        with patch("policyengine_api_tagger.api.revision_tagger._get_blob"):
            tagger = RevisionTagger("test-bucket")
            cleanup = RevisionCleanup(
                bucket_name="test-bucket",
                simulation_service_name="api-simulation",
                project_id="test-project",
                region="us-central1",
            )
            add_all_routes(app, tagger, cleanup)

            yield TestClient(app)

    def test_cleanup_returns_success_with_existing_revisions(
        self, client, mock_gcs, mock_cloudrun_revisions
    ):
        """Cleanup succeeds and returns existing revisions."""
        # Set up existing revisions in Cloud Run
        mock_cloudrun_revisions["revisions"].extend(["rev-1", "rev-2", "rev-3"])

        # Set up metadata files that all point to existing revisions
        mock_gcs["contents"]["us.1.0.0.json"] = json.dumps(
            {"revision": "projects/.../revisions/rev-1"}
        )
        mock_gcs["contents"]["uk.2.0.0.json"] = json.dumps(
            {"revision": "projects/.../revisions/rev-2"}
        )

        response = client.post("/cleanup")

        assert response.status_code == 200
        result = response.json()
        assert len(result["errors"]) == 0
        assert set(result["existing_revisions"]) == {"rev-1", "rev-2", "rev-3"}
        assert len(result["metadata_files_deleted"]) == 0
        assert len(result["metadata_files_kept"]) == 2

    def test_cleanup_deletes_stale_metadata_files(
        self, client, mock_gcs, mock_cloudrun_revisions
    ):
        """Cleanup deletes metadata files for non-existent revisions."""
        # Only rev-1 exists in Cloud Run
        mock_cloudrun_revisions["revisions"].append("rev-1")

        # Set up metadata files - one for existing revision, one for deleted
        mock_gcs["contents"]["us.1.0.0.json"] = json.dumps(
            {"revision": "projects/.../revisions/rev-1"}
        )
        mock_gcs["contents"]["us.0.9.0.json"] = json.dumps(
            {"revision": "projects/.../revisions/rev-deleted"}
        )

        response = client.post("/cleanup")

        assert response.status_code == 200
        result = response.json()
        assert len(result["errors"]) == 0
        assert result["metadata_files_deleted"] == ["us.0.9.0.json"]
        assert result["metadata_files_kept"] == ["us.1.0.0.json"]

        # Verify the file was actually deleted from mock storage
        assert "us.0.9.0.json" not in mock_gcs["contents"]
        assert "us.1.0.0.json" in mock_gcs["contents"]

    def test_cleanup_skips_special_files(
        self, client, mock_gcs, mock_cloudrun_revisions
    ):
        """Cleanup skips live.json and deployments.json."""
        mock_cloudrun_revisions["revisions"].append("rev-1")

        # Add special files that should not be deleted
        mock_gcs["contents"]["live.json"] = json.dumps({"revision": "rev-deleted"})
        mock_gcs["contents"]["deployments.json"] = json.dumps([])

        response = client.post("/cleanup")

        assert response.status_code == 200
        result = response.json()
        # Special files should still exist
        assert "live.json" in mock_gcs["contents"]
        assert "deployments.json" in mock_gcs["contents"]
        # They shouldn't appear in kept or deleted lists
        assert "live.json" not in result["metadata_files_kept"]
        assert "deployments.json" not in result["metadata_files_kept"]

    def test_cleanup_handles_empty_bucket(
        self, client, mock_gcs, mock_cloudrun_revisions
    ):
        """Cleanup succeeds with no metadata files."""
        mock_cloudrun_revisions["revisions"].extend(["rev-1", "rev-2"])
        # No metadata files in bucket

        response = client.post("/cleanup")

        assert response.status_code == 200
        result = response.json()
        assert len(result["errors"]) == 0
        assert result["metadata_files_deleted"] == []
        assert result["metadata_files_kept"] == []


# -----------------------------------------------------------------------------
# Cleanup endpoint without cleanup configured
# -----------------------------------------------------------------------------


class TestCleanupEndpointNotConfigured:
    """Tests behavior when cleanup is not configured."""

    @pytest.fixture
    def client_without_cleanup(self):
        """Create test client without cleanup configured."""
        app = FastAPI()

        with patch("policyengine_api_tagger.api.revision_tagger._get_blob"):
            tagger = RevisionTagger("test-bucket")
            # Pass None for cleanup
            add_all_routes(app, tagger, None)
            yield TestClient(app)

    def test_cleanup_returns_503_when_not_configured(self, client_without_cleanup):
        response = client_without_cleanup.post("/cleanup")

        assert response.status_code == 503
        assert "not configured" in response.json()["detail"]
