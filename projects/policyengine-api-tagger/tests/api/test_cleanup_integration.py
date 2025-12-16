"""Integration tests for the cleanup endpoint (with mocks)."""

from unittest.mock import AsyncMock, MagicMock, patch
import pytest
from fastapi.testclient import TestClient
from fastapi import FastAPI

from policyengine_api_tagger.api.revision_tagger import RevisionTagger
from policyengine_api_tagger.api.revision_cleanup import RevisionCleanup
from policyengine_api_tagger.api.routes import add_all_routes


def make_mock_traffic_entry(tag: str | None, revision: str, percent: int = 0):
    """Create a mock traffic entry."""
    entry = MagicMock()
    entry.tag = tag
    entry.revision = revision
    entry.percent = percent
    return entry


# -----------------------------------------------------------------------------
# Local Integration Tests (with mocks)
# -----------------------------------------------------------------------------


class TestCleanupEndpointLocal:
    """Tests the cleanup endpoint with mocked Cloud Run."""

    @pytest.fixture
    def mock_cloudrun_service(self):
        """Mock Cloud Run services client."""
        with patch(
            "policyengine_api_tagger.api.revision_cleanup.ServicesAsyncClient"
        ) as MockClient:
            mock_client = AsyncMock()
            MockClient.return_value = mock_client

            # Store mock service for manipulation in tests
            mock_service = MagicMock()
            mock_service.traffic = []

            async def mock_get_service(name):
                return mock_service

            mock_client.get_service = mock_get_service
            mock_client.update_service = AsyncMock()

            yield {
                "client": mock_client,
                "service": mock_service,
            }

    @pytest.fixture
    def client(self, mock_cloudrun_service):
        """Create test client with mocked dependencies."""
        app = FastAPI(
            title="policyengine-api-tagger-test",
            summary="Test instance",
        )

        # Mock the revision tagger's blob access
        with patch("policyengine_api_tagger.api.revision_tagger._get_blob"):
            tagger = RevisionTagger("test-bucket")
            cleanup = RevisionCleanup(
                project_id="test-project",
                region="us-central1",
                simulation_service_name="api-simulation",
            )
            add_all_routes(app, tagger, cleanup)

            yield TestClient(app)

    def test_cleanup_returns_success_with_tags(
        self, client, mock_cloudrun_service
    ):
        """Cleanup succeeds and returns tag information."""
        mock_cloudrun_service["service"].traffic = [
            make_mock_traffic_entry("country-us-model-1-459-0", "rev-us"),
            make_mock_traffic_entry("country-uk-model-2-65-9", "rev-uk"),
            make_mock_traffic_entry(None, "rev-main", percent=100),
        ]

        response = client.post("/cleanup?dry_run=true")

        assert response.status_code == 200
        result = response.json()
        assert len(result["errors"]) == 0
        assert result["total_tags_found"] == 2
        assert result["newest_us_tag"] == "country-us-model-1-459-0"
        assert result["newest_uk_tag"] == "country-uk-model-2-65-9"

    def test_cleanup_dry_run_does_not_modify(
        self, client, mock_cloudrun_service
    ):
        """Cleanup with dry_run=true should NOT call update_service."""
        mock_cloudrun_service["service"].traffic = [
            make_mock_traffic_entry("country-us-model-1-100-0", "rev-1"),
            make_mock_traffic_entry("country-us-model-1-200-0", "rev-2"),
            make_mock_traffic_entry("country-uk-model-2-50-0", "rev-3"),
        ]

        response = client.post("/cleanup?dry_run=true&keep=2")

        assert response.status_code == 200
        result = response.json()

        # Should show what would be removed
        assert len(result["tags_removed"]) == 1
        assert result["tags_removed"][0] == "country-us-model-1-100-0"

        # CRITICAL: update_service should NOT have been called
        mock_cloudrun_service["client"].update_service.assert_not_called()

    def test_cleanup_identifies_safeguards(
        self, client, mock_cloudrun_service
    ):
        """Cleanup correctly identifies newest US and UK tags."""
        mock_cloudrun_service["service"].traffic = [
            make_mock_traffic_entry("country-us-model-1-100-0", "rev-1"),
            make_mock_traffic_entry("country-us-model-1-459-0", "rev-2"),
            make_mock_traffic_entry("country-uk-model-2-30-0", "rev-3"),
            make_mock_traffic_entry("country-uk-model-2-65-9", "rev-4"),
        ]

        response = client.post("/cleanup?dry_run=true")

        assert response.status_code == 200
        result = response.json()
        assert result["newest_us_tag"] == "country-us-model-1-459-0"
        assert result["newest_uk_tag"] == "country-uk-model-2-65-9"

    def test_cleanup_respects_keep_count(
        self, client, mock_cloudrun_service
    ):
        """Cleanup keeps the correct number of tags."""
        mock_cloudrun_service["service"].traffic = [
            make_mock_traffic_entry("country-us-model-1-100-0", "rev-1"),
            make_mock_traffic_entry("country-us-model-1-200-0", "rev-2"),
            make_mock_traffic_entry("country-us-model-1-300-0", "rev-3"),
            make_mock_traffic_entry("country-us-model-1-400-0", "rev-4"),
            make_mock_traffic_entry("country-uk-model-2-50-0", "rev-5"),
        ]

        response = client.post("/cleanup?dry_run=true&keep=3")

        assert response.status_code == 200
        result = response.json()
        assert len(result["tags_kept"]) == 3
        assert len(result["tags_removed"]) == 2

    def test_cleanup_validates_keep_minimum(self, client, mock_cloudrun_service):
        """Cleanup rejects keep < 2."""
        response = client.post("/cleanup?keep=1")

        assert response.status_code == 400
        assert "at least 2" in response.json()["detail"]

    def test_cleanup_handles_no_tags(
        self, client, mock_cloudrun_service
    ):
        """Cleanup handles service with no tags."""
        mock_cloudrun_service["service"].traffic = [
            make_mock_traffic_entry(None, "rev-main", percent=100),
        ]

        response = client.post("/cleanup?dry_run=true")

        assert response.status_code == 200
        result = response.json()
        assert result["total_tags_found"] == 0
        assert result["tags_kept"] == []
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
        response = client_without_cleanup.post("/cleanup")

        assert response.status_code == 503
        assert "not configured" in response.json()["detail"]

    def test_cleanup_dry_run_also_returns_503(self, client_without_cleanup):
        """Even dry_run should return 503 if not configured."""
        response = client_without_cleanup.post("/cleanup?dry_run=true")

        assert response.status_code == 503
        assert "not configured" in response.json()["detail"]
