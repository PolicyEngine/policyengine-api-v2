"""
Integration tests for the tagger API cleanup endpoint.

These tests run against real GCP infrastructure using dry_run=true
to ensure they are NON-DESTRUCTIVE.

CRITICAL: All tests MUST use dry_run=true to prevent any modifications.
"""

import pytest
import httpx


@pytest.mark.requires_gcp
class TestCleanupEndpointDryRun:
    """
    Tests for the /cleanup endpoint using dry_run mode.

    These tests are marked:
    - requires_gcp: They need real GCP credentials (excluded from PR tests)

    These tests run on BOTH beta and production because they use dry_run=true
    and therefore make NO CHANGES to the service.

    IMPORTANT: Every test in this class MUST use dry_run=true.
    """

    def test_cleanup_dry_run_responds(self, tagger_client: httpx.Client):
        """Verify the cleanup endpoint responds in dry_run mode."""
        # CRITICAL: dry_run=true ensures no changes are made
        response = tagger_client.post("/cleanup?dry_run=true")

        assert response.status_code == 200

        result = response.json()
        assert "total_tags_found" in result
        assert "tags_kept" in result
        assert "tags_removed" in result
        assert "newest_us_tag" in result
        assert "newest_uk_tag" in result
        assert "errors" in result

    def test_cleanup_dry_run_finds_tags(self, tagger_client: httpx.Client):
        """Verify dry_run finds existing traffic tags."""
        # CRITICAL: dry_run=true ensures no changes are made
        response = tagger_client.post("/cleanup?dry_run=true")

        assert response.status_code == 200
        result = response.json()

        # Should have found at least some tags (we know there are 84+ in beta)
        assert result["total_tags_found"] > 0, (
            "Expected to find at least one traffic tag"
        )

    def test_cleanup_dry_run_identifies_safeguards(self, tagger_client: httpx.Client):
        """Verify dry_run identifies newest US and UK tags."""
        # CRITICAL: dry_run=true ensures no changes are made
        response = tagger_client.post("/cleanup?dry_run=true")

        assert response.status_code == 200
        result = response.json()

        # Should identify safeguards if there are any tags
        if result["total_tags_found"] > 0:
            # At least one safeguard should be identified
            has_safeguard = (
                result["newest_us_tag"] is not None or
                result["newest_uk_tag"] is not None
            )
            assert has_safeguard, "Expected at least one safeguard tag to be identified"

    def test_cleanup_dry_run_respects_keep_count(self, tagger_client: httpx.Client):
        """Verify dry_run respects the keep parameter."""
        # CRITICAL: dry_run=true ensures no changes are made
        response = tagger_client.post("/cleanup?dry_run=true&keep=5")

        assert response.status_code == 200
        result = response.json()

        # If there are more than 5 tags, should plan to keep only 5
        if result["total_tags_found"] > 5:
            assert len(result["tags_kept"]) == 5
            assert len(result["tags_removed"]) == result["total_tags_found"] - 5

    def test_cleanup_dry_run_reports_no_errors(self, tagger_client: httpx.Client):
        """Verify dry_run completes without errors."""
        # CRITICAL: dry_run=true ensures no changes are made
        response = tagger_client.post("/cleanup?dry_run=true")

        assert response.status_code == 200
        result = response.json()

        assert len(result["errors"]) == 0, (
            f"Unexpected errors during dry_run: {result['errors']}"
        )

    def test_cleanup_dry_run_tag_format(self, tagger_client: httpx.Client):
        """Verify tags follow expected format."""
        # CRITICAL: dry_run=true ensures no changes are made
        response = tagger_client.post("/cleanup?dry_run=true")

        assert response.status_code == 200
        result = response.json()

        # Check that all kept tags follow the expected format
        for tag in result["tags_kept"]:
            assert tag.startswith("country-us-model-") or tag.startswith("country-uk-model-"), (
                f"Tag '{tag}' doesn't follow expected format"
            )

    def test_cleanup_rejects_keep_less_than_2(self, tagger_client: httpx.Client):
        """Verify cleanup rejects keep < 2."""
        response = tagger_client.post("/cleanup?dry_run=true&keep=1")

        assert response.status_code == 400
        assert "at least 2" in response.json()["detail"]
