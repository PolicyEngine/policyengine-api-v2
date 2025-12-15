"""Integration tests for the cleanup endpoint."""

from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timedelta
import json
import pytest
from fastapi.testclient import TestClient
from fastapi import FastAPI

from google.cloud.run_v2 import TrafficTarget, Service

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

            def copy_blob(source_blob, dest_bucket, dest_name):
                bucket_contents[dest_name] = bucket_contents.get(source_blob.name, "")

            mock_bucket.copy_blob = copy_blob

            def list_blobs():
                return [mock_blob(name) for name in bucket_contents.keys()]

            mock_bucket.list_blobs = list_blobs

            yield {
                "client": mock_client,
                "bucket": mock_bucket,
                "contents": bucket_contents,
            }

    @pytest.fixture
    def mock_cloudrun(self):
        """Mock Cloud Run services client."""
        with patch(
            "policyengine_api_tagger.api.revision_cleanup.ServicesAsyncClient"
        ) as MockClient:
            mock_client = AsyncMock()
            MockClient.return_value = mock_client

            # Create a mock service with traffic
            service = Service()
            service.uri = "https://api-simulation.run.app"
            service.traffic = []

            mock_client.get_service.return_value = service

            yield {
                "client": mock_client,
                "service": service,
            }

    @pytest.fixture
    def client(self, mock_gcs, mock_cloudrun):
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

    def test_cleanup_returns_400_for_invalid_keep_count(self, client):
        response = client.post("/cleanup?keep=0")
        assert response.status_code == 400
        assert "at least 1" in response.json()["detail"]

    def test_cleanup_returns_error_when_no_manifest(self, client, mock_gcs):
        # No manifest in bucket
        response = client.post("/cleanup?keep=5")

        assert response.status_code == 200
        result = response.json()
        assert "No deployment manifest found" in result["errors"]
        assert result["revisions_kept"] == []

    def test_cleanup_with_manifest_returns_success(
        self, client, mock_gcs, mock_cloudrun
    ):
        # Set up manifest with deployments
        # Most recent (i=0) has highest versions (realistic deployment pattern)
        now = datetime.now()
        manifest = [
            {
                "revision": f"rev-{i}",
                "us": f"1.{6 - i}.0",  # rev-0 has 1.6.0 (highest), rev-6 has 1.0.0
                "uk": f"2.{6 - i}.0",
                "deployed_at": (now - timedelta(days=i)).isoformat(),
            }
            for i in range(7)
        ]
        mock_gcs["contents"]["deployments.json"] = json.dumps(manifest)

        # Set up metadata files
        for i in range(7):
            mock_gcs["contents"][f"us.1.{6 - i}.0.json"] = json.dumps(
                {"revision": f"rev-{i}"}
            )
            mock_gcs["contents"][f"uk.2.{6 - i}.0.json"] = json.dumps(
                {"revision": f"rev-{i}"}
            )

        # Set up Cloud Run service with tags
        # rev-0 has 100% traffic (most recent), rev-1 and rev-2 have tags
        mock_cloudrun["service"].traffic = [
            TrafficTarget(percent=100, revision="rev-0"),
            TrafficTarget(percent=0, revision="rev-1", tag="country-us-model-1-5-0"),
            TrafficTarget(percent=0, revision="rev-2", tag="country-us-model-1-4-0"),
        ]

        response = client.post("/cleanup?keep=5")

        assert response.status_code == 200
        result = response.json()
        assert len(result["errors"]) == 0
        assert len(result["revisions_kept"]) == 5

    def test_cleanup_preserves_main_traffic_route(
        self, client, mock_gcs, mock_cloudrun
    ):
        """Ensure traffic with percent > 0 is never removed."""
        now = datetime.now()
        manifest = [
            {
                "revision": "rev-new",
                "us": "1.0.0",
                "uk": "2.0.0",
                "deployed_at": now.isoformat(),
            }
        ]
        mock_gcs["contents"]["deployments.json"] = json.dumps(manifest)

        # Main traffic points to revision NOT in manifest
        mock_cloudrun["service"].traffic = [
            TrafficTarget(percent=100, revision="rev-not-in-manifest"),
        ]

        response = client.post("/cleanup?keep=5")

        assert response.status_code == 200
        # Should not have tried to remove the main traffic route
        result = response.json()
        assert result["tags_removed"] == []


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
        response = client_without_cleanup.post("/cleanup?keep=5")

        assert response.status_code == 503
        assert "not configured" in response.json()["detail"]
