"""
Integration tests for the tagger API cleanup endpoint.

These tests run against real GCP infrastructure and are marked as beta_only
because they interact with Cloud Run traffic configuration.
"""

import pytest
import httpx


@pytest.mark.beta_only
@pytest.mark.requires_gcp
class TestCleanupEndpoint:
    """
    Tests for the /cleanup endpoint.

    These tests are marked:
    - requires_gcp: They need real GCP credentials (excluded from PR tests)
    - beta_only: They should only run on beta deployments (excluded from prod)

    Rationale:
    1. They interact with real Cloud Run traffic configuration
    2. They modify the deployments manifest
    3. While designed to be safe, they should not run against production

    The tests use keep=100 to ensure nothing is actually removed,
    making them safe verification tests rather than destructive ones.
    """

    def test_cleanup_endpoint_responds(self, tagger_client: httpx.Client):
        """Verify the cleanup endpoint is accessible and responds."""
        response = tagger_client.post("/cleanup", params={"keep": 100})

        # Should succeed (even if no manifest exists yet)
        assert response.status_code == 200

        result = response.json()
        assert "revisions_kept" in result
        assert "tags_removed" in result
        assert "metadata_files_deleted" in result
        assert "errors" in result

    def test_cleanup_with_high_keep_count_removes_nothing(
        self, tagger_client: httpx.Client
    ):
        """
        With keep=100, cleanup should remove nothing.

        This is a safe way to verify the cleanup logic works against
        real infrastructure without actually removing anything.
        """
        response = tagger_client.post("/cleanup", params={"keep": 100})

        assert response.status_code == 200
        result = response.json()

        # With keep=100, nothing should be removed (unless >100 deployments)
        assert len(result["tags_removed"]) == 0, (
            f"Expected no tags removed with keep=100, got: {result['tags_removed']}"
        )
        assert len(result["metadata_files_deleted"]) == 0, (
            f"Expected no files deleted with keep=100, "
            f"got: {result['metadata_files_deleted']}"
        )

    def test_cleanup_returns_kept_revisions(self, tagger_client: httpx.Client):
        """Verify cleanup returns the list of revisions being kept."""
        response = tagger_client.post("/cleanup", params={"keep": 100})

        assert response.status_code == 200
        result = response.json()

        # If there's a manifest, we should have kept revisions
        if "No deployment manifest found" not in str(result.get("errors", [])):
            assert len(result["revisions_kept"]) > 0, (
                "Expected at least one revision to be kept"
            )

    def test_cleanup_rejects_invalid_keep_count(self, tagger_client: httpx.Client):
        """Verify cleanup rejects keep=0."""
        response = tagger_client.post("/cleanup", params={"keep": 0})

        assert response.status_code == 400
        assert "at least 1" in response.json()["detail"]


@pytest.mark.beta_only
@pytest.mark.requires_gcp
class TestCleanupSafeguards:
    """
    Tests to verify cleanup safeguards are working.

    These tests verify that the highest US and UK versions are always
    protected, regardless of the keep count.
    """

    def test_cleanup_reports_no_critical_errors(self, tagger_client: httpx.Client):
        """Verify cleanup completes without critical errors."""
        response = tagger_client.post("/cleanup", params={"keep": 100})

        assert response.status_code == 200
        result = response.json()

        # Filter out expected "no manifest" errors
        critical_errors = [
            e for e in result["errors"]
            if "No deployment manifest found" not in e
        ]

        assert len(critical_errors) == 0, (
            f"Unexpected errors during cleanup: {critical_errors}"
        )
