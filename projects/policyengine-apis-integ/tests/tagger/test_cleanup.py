"""
Integration tests for the tagger API cleanup endpoint.

These tests run against real GCP infrastructure and are marked as beta_only
because they interact with Cloud Run revision data.
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
    1. They query real Cloud Run revision data
    2. They may delete stale metadata files
    3. While designed to be safe, they should not run against production
    """

    def test_cleanup_endpoint_responds(self, tagger_client: httpx.Client):
        """Verify the cleanup endpoint is accessible and responds."""
        response = tagger_client.post("/cleanup")

        # Should succeed
        assert response.status_code == 200

        result = response.json()
        assert "existing_revisions" in result
        assert "metadata_files_deleted" in result
        assert "metadata_files_kept" in result
        assert "errors" in result

    def test_cleanup_returns_existing_revisions(self, tagger_client: httpx.Client):
        """Verify cleanup returns the list of existing revisions from Cloud Run."""
        response = tagger_client.post("/cleanup")

        assert response.status_code == 200
        result = response.json()

        # Should have found at least one revision (the current deployment)
        assert len(result["existing_revisions"]) > 0, (
            "Expected at least one existing revision"
        )

    def test_cleanup_reports_no_critical_errors(self, tagger_client: httpx.Client):
        """Verify cleanup completes without critical errors."""
        response = tagger_client.post("/cleanup")

        assert response.status_code == 200
        result = response.json()

        # Filter out expected transient errors
        critical_errors = [
            e for e in result["errors"]
            if "Failed to list revisions" not in e  # API might be briefly unavailable
        ]

        assert len(critical_errors) == 0, (
            f"Unexpected errors during cleanup: {critical_errors}"
        )
