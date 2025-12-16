"""Unit tests for revision_cleanup module (tag-based cleanup)."""

from unittest.mock import AsyncMock, MagicMock, patch
import pytest

from policyengine_api_tagger.api.revision_cleanup import (
    RevisionCleanup,
    CleanupResult,
    TagInfo,
)


# -----------------------------------------------------------------------------
# Test Fixtures
# -----------------------------------------------------------------------------


@pytest.fixture
def cleanup():
    """Create a RevisionCleanup instance for testing."""
    return RevisionCleanup(
        project_id="test-project",
        region="us-central1",
        simulation_service_name="api-simulation",
    )


def make_mock_traffic_entry(tag: str | None, revision: str, percent: int = 0):
    """Create a mock traffic entry."""
    entry = MagicMock()
    entry.tag = tag
    entry.revision = revision
    entry.percent = percent
    return entry


# -----------------------------------------------------------------------------
# Tests for _extract_deploy_timestamp
# -----------------------------------------------------------------------------


class TestExtractDeployTimestamp:
    def test_extracts_timestamp_from_standard_revision(self, cleanup):
        """Should extract timestamp from standard revision name format."""
        result = cleanup._extract_deploy_timestamp("api-simulation-abc123-20251216101118")
        assert result == "20251216101118"

    def test_extracts_timestamp_from_longer_revision(self, cleanup):
        """Should extract timestamp from revision with multiple dashes."""
        result = cleanup._extract_deploy_timestamp(
            "api-simulation-some-extra-parts-20251201123456"
        )
        assert result == "20251201123456"

    def test_returns_empty_for_short_revision(self, cleanup):
        """Should return empty string for revisions without proper timestamp."""
        result = cleanup._extract_deploy_timestamp("rev-abc")
        assert result == ""

    def test_returns_empty_for_non_numeric_suffix(self, cleanup):
        """Should return empty string if last part is not numeric."""
        result = cleanup._extract_deploy_timestamp("api-simulation-abc-notanumber")
        assert result == ""

    def test_returns_empty_for_wrong_length_number(self, cleanup):
        """Should return empty string if number is not 14 digits."""
        result = cleanup._extract_deploy_timestamp("api-simulation-abc-12345")
        assert result == ""


# -----------------------------------------------------------------------------
# Tests for _parse_tag
# -----------------------------------------------------------------------------


class TestParseTag:
    def test_parses_us_tag(self, cleanup):
        result = cleanup._parse_tag("country-us-model-1-459-0", "rev-abc123")

        assert result is not None
        assert result.tag == "country-us-model-1-459-0"
        assert result.revision == "rev-abc123"
        assert result.country == "us"
        assert result.version == (1, 459, 0)
        assert result.version_str == "1.459.0"

    def test_parses_uk_tag(self, cleanup):
        result = cleanup._parse_tag("country-uk-model-2-65-9", "rev-def456")

        assert result is not None
        assert result.tag == "country-uk-model-2-65-9"
        assert result.revision == "rev-def456"
        assert result.country == "uk"
        assert result.version == (2, 65, 9)
        assert result.version_str == "2.65.9"

    def test_returns_none_for_invalid_country(self, cleanup):
        result = cleanup._parse_tag("country-fr-model-1-0-0", "rev-abc")
        assert result is None

    def test_returns_none_for_wrong_format(self, cleanup):
        result = cleanup._parse_tag("some-random-tag", "rev-abc")
        assert result is None

    def test_returns_none_for_non_numeric_version(self, cleanup):
        result = cleanup._parse_tag("country-us-model-abc-def", "rev-abc")
        assert result is None

    def test_handles_single_digit_version(self, cleanup):
        result = cleanup._parse_tag("country-us-model-1", "rev-abc")

        assert result is not None
        assert result.version == (1,)
        assert result.version_str == "1"


# -----------------------------------------------------------------------------
# Tests for _analyze_tags
# -----------------------------------------------------------------------------


class TestAnalyzeTags:
    @pytest.mark.asyncio
    async def test_identifies_newest_us_and_uk_tags(self, cleanup):
        """Should correctly identify newest US and UK tags as safeguards."""
        mock_service = MagicMock()
        mock_service.traffic = [
            make_mock_traffic_entry("country-us-model-1-100-0", "rev-us-old"),
            make_mock_traffic_entry("country-us-model-1-459-0", "rev-us-new"),
            make_mock_traffic_entry("country-uk-model-2-50-0", "rev-uk-old"),
            make_mock_traffic_entry("country-uk-model-2-65-9", "rev-uk-new"),
            make_mock_traffic_entry(None, "rev-main", percent=100),  # Main traffic
        ]

        with patch.object(cleanup, "_get_service", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_service

            (
                service,
                all_tags,
                tags_to_keep,
                newest_us,
                newest_uk,
                tags_removed,
                errors,
            ) = await cleanup._analyze_tags(keep_count=40)

        assert newest_us is not None
        assert newest_us.tag == "country-us-model-1-459-0"
        assert newest_uk is not None
        assert newest_uk.tag == "country-uk-model-2-65-9"
        assert len(errors) == 0

    @pytest.mark.asyncio
    async def test_keeps_safeguards_plus_newest(self, cleanup):
        """Should keep safeguards + next newest tags up to keep_count."""
        mock_service = MagicMock()
        mock_service.traffic = [
            make_mock_traffic_entry("country-us-model-1-100-0", "rev-1"),
            make_mock_traffic_entry("country-us-model-1-200-0", "rev-2"),
            make_mock_traffic_entry("country-us-model-1-300-0", "rev-3"),
            make_mock_traffic_entry("country-us-model-1-400-0", "rev-4"),  # Newest US
            make_mock_traffic_entry("country-uk-model-2-50-0", "rev-5"),
            make_mock_traffic_entry("country-uk-model-2-60-0", "rev-6"),  # Newest UK
        ]

        with patch.object(cleanup, "_get_service", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_service

            (
                service,
                all_tags,
                tags_to_keep,
                newest_us,
                newest_uk,
                tags_removed,
                errors,
            ) = await cleanup._analyze_tags(keep_count=4)

        # Should keep: newest US, newest UK, then next 2 newest by version
        assert len(tags_to_keep) == 4
        kept_tags = [t.tag for t in tags_to_keep]

        # Safeguards must be first
        assert "country-us-model-1-400-0" in kept_tags
        assert "country-uk-model-2-60-0" in kept_tags

        # Should remove oldest
        assert len(tags_removed) == 2

    @pytest.mark.asyncio
    async def test_handles_keep_count_less_than_2(self, cleanup):
        """Should enforce minimum keep_count of 2."""
        mock_service = MagicMock()
        mock_service.traffic = [
            make_mock_traffic_entry("country-us-model-1-400-0", "rev-us"),
            make_mock_traffic_entry("country-uk-model-2-60-0", "rev-uk"),
        ]

        with patch.object(cleanup, "_get_service", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_service

            (
                service,
                all_tags,
                tags_to_keep,
                newest_us,
                newest_uk,
                tags_removed,
                errors,
            ) = await cleanup._analyze_tags(keep_count=1)  # Should become 2

        # Should still keep both safeguards
        assert len(tags_to_keep) == 2

    @pytest.mark.asyncio
    async def test_handles_no_tags(self, cleanup):
        """Should handle service with no tags gracefully."""
        mock_service = MagicMock()
        mock_service.traffic = [
            make_mock_traffic_entry(None, "rev-main", percent=100),
        ]

        with patch.object(cleanup, "_get_service", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_service

            (
                service,
                all_tags,
                tags_to_keep,
                newest_us,
                newest_uk,
                tags_removed,
                errors,
            ) = await cleanup._analyze_tags(keep_count=40)

        assert len(all_tags) == 0
        assert len(tags_to_keep) == 0
        assert newest_us is None
        assert newest_uk is None

    @pytest.mark.asyncio
    async def test_handles_only_us_tags(self, cleanup):
        """Should handle service with only US tags."""
        mock_service = MagicMock()
        mock_service.traffic = [
            make_mock_traffic_entry("country-us-model-1-100-0", "rev-1"),
            make_mock_traffic_entry("country-us-model-1-200-0", "rev-2"),
        ]

        with patch.object(cleanup, "_get_service", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_service

            (
                service,
                all_tags,
                tags_to_keep,
                newest_us,
                newest_uk,
                tags_removed,
                errors,
            ) = await cleanup._analyze_tags(keep_count=40)

        assert newest_us is not None
        assert newest_us.tag == "country-us-model-1-200-0"
        assert newest_uk is None

    @pytest.mark.asyncio
    async def test_handles_service_error(self, cleanup):
        """Should handle service fetch errors gracefully."""
        with patch.object(cleanup, "_get_service", new_callable=AsyncMock) as mock_get:
            mock_get.side_effect = Exception("Cloud Run API error")

            (
                service,
                all_tags,
                tags_to_keep,
                newest_us,
                newest_uk,
                tags_removed,
                errors,
            ) = await cleanup._analyze_tags(keep_count=40)

        assert service is None
        assert len(errors) == 1
        assert "Failed to get service" in errors[0]


# -----------------------------------------------------------------------------
# Tests for preview
# -----------------------------------------------------------------------------


class TestPreview:
    @pytest.mark.asyncio
    async def test_returns_cleanup_result_without_changes(self, cleanup):
        """Preview should return what would happen without making changes."""
        mock_service = MagicMock()
        mock_service.traffic = [
            make_mock_traffic_entry("country-us-model-1-100-0", "rev-1"),
            make_mock_traffic_entry("country-us-model-1-200-0", "rev-2"),
            make_mock_traffic_entry("country-uk-model-2-50-0", "rev-3"),
        ]

        with patch.object(cleanup, "_get_service", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_service

            result = await cleanup.preview(keep_count=2)

        assert isinstance(result, CleanupResult)
        assert result.total_tags_found == 3
        assert result.newest_us_tag == "country-us-model-1-200-0"
        assert result.newest_uk_tag == "country-uk-model-2-50-0"
        # With keep=2, should remove oldest US tag
        assert len(result.tags_kept) == 2
        assert len(result.tags_removed) == 1

    @pytest.mark.asyncio
    async def test_preview_does_not_call_update(self, cleanup):
        """Preview should NOT call _update_service_traffic."""
        mock_service = MagicMock()
        mock_service.traffic = [
            make_mock_traffic_entry("country-us-model-1-100-0", "rev-1"),
            make_mock_traffic_entry("country-us-model-1-200-0", "rev-2"),
        ]

        with (
            patch.object(cleanup, "_get_service", new_callable=AsyncMock) as mock_get,
            patch.object(
                cleanup, "_update_service_traffic", new_callable=AsyncMock
            ) as mock_update,
        ):
            mock_get.return_value = mock_service

            await cleanup.preview(keep_count=1)

        # CRITICAL: update should NOT be called
        mock_update.assert_not_called()


# -----------------------------------------------------------------------------
# Tests for cleanup
# -----------------------------------------------------------------------------


class TestCleanup:
    @pytest.mark.asyncio
    async def test_calls_update_when_tags_to_remove(self, cleanup):
        """Cleanup should call update when there are tags to remove."""
        mock_service = MagicMock()
        mock_service.traffic = [
            make_mock_traffic_entry("country-us-model-1-100-0", "rev-1"),
            make_mock_traffic_entry("country-us-model-1-200-0", "rev-2"),
            make_mock_traffic_entry("country-uk-model-2-50-0", "rev-3"),
        ]

        with (
            patch.object(cleanup, "_get_service", new_callable=AsyncMock) as mock_get,
            patch.object(
                cleanup, "_update_service_traffic", new_callable=AsyncMock
            ) as mock_update,
        ):
            mock_get.return_value = mock_service

            result = await cleanup.cleanup(keep_count=2)

        # Should call update since there are tags to remove
        mock_update.assert_called_once()
        assert len(result.tags_removed) == 1

    @pytest.mark.asyncio
    async def test_does_not_call_update_when_nothing_to_remove(self, cleanup):
        """Cleanup should not call update when all tags are kept."""
        mock_service = MagicMock()
        mock_service.traffic = [
            make_mock_traffic_entry("country-us-model-1-200-0", "rev-1"),
            make_mock_traffic_entry("country-uk-model-2-50-0", "rev-2"),
        ]

        with (
            patch.object(cleanup, "_get_service", new_callable=AsyncMock) as mock_get,
            patch.object(
                cleanup, "_update_service_traffic", new_callable=AsyncMock
            ) as mock_update,
        ):
            mock_get.return_value = mock_service

            result = await cleanup.cleanup(keep_count=40)  # Keep all

        # Should NOT call update since nothing to remove
        mock_update.assert_not_called()
        assert len(result.tags_removed) == 0

    @pytest.mark.asyncio
    async def test_handles_update_failure(self, cleanup):
        """Cleanup should handle update failures gracefully."""
        mock_service = MagicMock()
        mock_service.traffic = [
            make_mock_traffic_entry("country-us-model-1-100-0", "rev-1"),
            make_mock_traffic_entry("country-us-model-1-200-0", "rev-2"),
            make_mock_traffic_entry("country-us-model-1-300-0", "rev-3"),
            make_mock_traffic_entry("country-uk-model-2-50-0", "rev-4"),
        ]

        with (
            patch.object(cleanup, "_get_service", new_callable=AsyncMock) as mock_get,
            patch.object(
                cleanup, "_update_service_traffic", new_callable=AsyncMock
            ) as mock_update,
        ):
            mock_get.return_value = mock_service
            mock_update.side_effect = Exception("Update failed")

            # keep=2 means keep safeguards only, remove the other 2
            result = await cleanup.cleanup(keep_count=2)

        # Should return error and report no tags removed
        assert len(result.errors) == 1
        assert "Failed to update service traffic" in result.errors[0]
        assert len(result.tags_removed) == 0  # Nothing actually removed

    @pytest.mark.asyncio
    async def test_preserves_main_traffic_entries(self, cleanup):
        """Update should preserve traffic entries with percent > 0."""
        mock_service = MagicMock()
        mock_service.traffic = [
            make_mock_traffic_entry("country-us-model-1-100-0", "rev-1"),
            make_mock_traffic_entry("country-us-model-1-200-0", "rev-2"),
            make_mock_traffic_entry("country-us-model-1-300-0", "rev-3"),
            make_mock_traffic_entry("country-uk-model-2-50-0", "rev-4"),
            make_mock_traffic_entry(None, "rev-main", percent=100),  # Main traffic
        ]

        captured_tags_to_keep = []

        async def capture_update(service, tags_to_keep):
            captured_tags_to_keep.extend(tags_to_keep)

        with (
            patch.object(cleanup, "_get_service", new_callable=AsyncMock) as mock_get,
            patch.object(
                cleanup, "_update_service_traffic", side_effect=capture_update
            ) as mock_update,
        ):
            mock_get.return_value = mock_service

            # keep=2 means only safeguards, should remove 2 tags
            await cleanup.cleanup(keep_count=2)

        # The tags_to_keep passed to update should only include tagged entries
        # Main traffic (percent=100) handling is in _update_service_traffic itself
        mock_update.assert_called_once()
        # Should have passed 2 tags to keep (newest US + newest UK)
        assert len(captured_tags_to_keep) == 2


# -----------------------------------------------------------------------------
# Tests for version comparison and timestamp sorting
# -----------------------------------------------------------------------------


class TestVersionComparison:
    @pytest.mark.asyncio
    async def test_safeguards_use_version_comparison(self, cleanup):
        """Newest US and UK safeguards should be identified by version number."""
        mock_service = MagicMock()
        # These would sort wrong lexicographically: 1-9-0 > 1-10-0 > 1-100-0
        mock_service.traffic = [
            make_mock_traffic_entry(
                "country-us-model-1-9-0", "api-simulation-abc-20251210100000"
            ),
            make_mock_traffic_entry(
                "country-us-model-1-100-0", "api-simulation-def-20251211100000"
            ),
            make_mock_traffic_entry(
                "country-us-model-1-10-0", "api-simulation-ghi-20251212100000"
            ),
        ]

        with patch.object(cleanup, "_get_service", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_service

            (
                service,
                all_tags,
                tags_to_keep,
                newest_us,
                newest_uk,
                tags_removed,
                errors,
            ) = await cleanup._analyze_tags(keep_count=2)

        # 1.100.0 > 1.10.0 > 1.9.0 numerically - safeguards use version comparison
        assert newest_us.tag == "country-us-model-1-100-0"

    @pytest.mark.asyncio
    async def test_remaining_slots_use_timestamp_sorting(self, cleanup):
        """After safeguards, remaining slots should be filled by deployment timestamp."""
        mock_service = MagicMock()
        # US version 1.100.0 is newest US by version but was deployed earlier
        # US version 1.9.0 is oldest by version but deployed most recently
        mock_service.traffic = [
            make_mock_traffic_entry(
                "country-us-model-1-9-0", "api-simulation-abc-20251215100000"
            ),  # Most recent deploy
            make_mock_traffic_entry(
                "country-us-model-1-100-0", "api-simulation-def-20251210100000"
            ),  # Oldest deploy
            make_mock_traffic_entry(
                "country-us-model-1-10-0", "api-simulation-ghi-20251212100000"
            ),  # Middle deploy
            make_mock_traffic_entry(
                "country-uk-model-2-50-0", "api-simulation-jkl-20251214100000"
            ),  # UK safeguard
        ]

        with patch.object(cleanup, "_get_service", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_service

            (
                service,
                all_tags,
                tags_to_keep,
                newest_us,
                newest_uk,
                tags_removed,
                errors,
            ) = await cleanup._analyze_tags(keep_count=3)

        # Safeguards: US 1.100.0 (highest US version), UK 2.50.0 (highest UK version)
        assert newest_us.tag == "country-us-model-1-100-0"
        assert newest_uk.tag == "country-uk-model-2-50-0"

        # With keep=3: safeguards (US 1.100.0 + UK 2.50.0) + 1 more by timestamp
        # The next most recent by timestamp is US 1.9.0 (20251215100000)
        kept_tags = [t.tag for t in tags_to_keep]
        assert len(kept_tags) == 3
        assert "country-us-model-1-100-0" in kept_tags  # US safeguard
        assert "country-uk-model-2-50-0" in kept_tags  # UK safeguard
        assert "country-us-model-1-9-0" in kept_tags  # Most recent by timestamp

        # US 1.10.0 should be removed (oldest timestamp after safeguards excluded)
        assert "country-us-model-1-10-0" in tags_removed

    @pytest.mark.asyncio
    async def test_mixed_us_uk_sorted_by_timestamp(self, cleanup):
        """US and UK tags should be mixed when sorting by timestamp."""
        mock_service = MagicMock()
        # Mix of US and UK with timestamps - should keep by deploy time, not by country
        mock_service.traffic = [
            make_mock_traffic_entry(
                "country-us-model-1-400-0", "api-simulation-us1-20251210100000"
            ),  # Oldest
            make_mock_traffic_entry(
                "country-uk-model-2-60-0", "api-simulation-uk1-20251211100000"
            ),  # 2nd oldest
            make_mock_traffic_entry(
                "country-us-model-1-300-0", "api-simulation-us2-20251212100000"
            ),  # Middle
            make_mock_traffic_entry(
                "country-uk-model-2-50-0", "api-simulation-uk2-20251213100000"
            ),  # 2nd newest
            make_mock_traffic_entry(
                "country-us-model-1-200-0", "api-simulation-us3-20251214100000"
            ),  # Newest
        ]

        with patch.object(cleanup, "_get_service", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_service

            (
                service,
                all_tags,
                tags_to_keep,
                newest_us,
                newest_uk,
                tags_removed,
                errors,
            ) = await cleanup._analyze_tags(keep_count=4)

        # Safeguards by version: US 1.400.0, UK 2.60.0
        assert newest_us.tag == "country-us-model-1-400-0"
        assert newest_uk.tag == "country-uk-model-2-60-0"

        # With keep=4:
        # - US 1.400.0 (safeguard by version)
        # - UK 2.60.0 (safeguard by version)
        # - US 1.200.0 (most recent by timestamp: 20251214)
        # - UK 2.50.0 (2nd most recent by timestamp: 20251213)
        kept_tags = [t.tag for t in tags_to_keep]
        assert len(kept_tags) == 4
        assert "country-us-model-1-400-0" in kept_tags
        assert "country-uk-model-2-60-0" in kept_tags
        assert "country-us-model-1-200-0" in kept_tags
        assert "country-uk-model-2-50-0" in kept_tags

        # US 1.300.0 should be removed
        assert "country-us-model-1-300-0" in tags_removed
