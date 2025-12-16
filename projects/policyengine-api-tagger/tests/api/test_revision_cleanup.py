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

            service, all_tags, tags_to_keep, newest_us, newest_uk, tags_removed, errors = \
                await cleanup._analyze_tags(keep_count=40)

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

            service, all_tags, tags_to_keep, newest_us, newest_uk, tags_removed, errors = \
                await cleanup._analyze_tags(keep_count=4)

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

            service, all_tags, tags_to_keep, newest_us, newest_uk, tags_removed, errors = \
                await cleanup._analyze_tags(keep_count=1)  # Should become 2

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

            service, all_tags, tags_to_keep, newest_us, newest_uk, tags_removed, errors = \
                await cleanup._analyze_tags(keep_count=40)

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

            service, all_tags, tags_to_keep, newest_us, newest_uk, tags_removed, errors = \
                await cleanup._analyze_tags(keep_count=40)

        assert newest_us is not None
        assert newest_us.tag == "country-us-model-1-200-0"
        assert newest_uk is None

    @pytest.mark.asyncio
    async def test_handles_service_error(self, cleanup):
        """Should handle service fetch errors gracefully."""
        with patch.object(cleanup, "_get_service", new_callable=AsyncMock) as mock_get:
            mock_get.side_effect = Exception("Cloud Run API error")

            service, all_tags, tags_to_keep, newest_us, newest_uk, tags_removed, errors = \
                await cleanup._analyze_tags(keep_count=40)

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
            patch.object(cleanup, "_update_service_traffic", new_callable=AsyncMock) as mock_update,
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
            patch.object(cleanup, "_update_service_traffic", new_callable=AsyncMock) as mock_update,
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
            patch.object(cleanup, "_update_service_traffic", new_callable=AsyncMock) as mock_update,
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
            patch.object(cleanup, "_update_service_traffic", new_callable=AsyncMock) as mock_update,
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
            patch.object(cleanup, "_update_service_traffic", side_effect=capture_update) as mock_update,
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
# Tests for version comparison
# -----------------------------------------------------------------------------


class TestVersionComparison:
    @pytest.mark.asyncio
    async def test_sorts_versions_correctly(self, cleanup):
        """Should sort versions numerically, not lexicographically."""
        mock_service = MagicMock()
        # These would sort wrong lexicographically: 1-9-0 > 1-10-0 > 1-100-0
        mock_service.traffic = [
            make_mock_traffic_entry("country-us-model-1-9-0", "rev-1"),
            make_mock_traffic_entry("country-us-model-1-100-0", "rev-2"),
            make_mock_traffic_entry("country-us-model-1-10-0", "rev-3"),
        ]

        with patch.object(cleanup, "_get_service", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_service

            service, all_tags, tags_to_keep, newest_us, newest_uk, tags_removed, errors = \
                await cleanup._analyze_tags(keep_count=2)

        # 1.100.0 > 1.10.0 > 1.9.0 numerically
        assert newest_us.tag == "country-us-model-1-100-0"

        # With keep=2, should keep 1.100.0 and 1.10.0, remove 1.9.0
        kept_tags = [t.tag for t in tags_to_keep]
        assert "country-us-model-1-100-0" in kept_tags
        assert "country-us-model-1-10-0" in kept_tags
        assert "country-us-model-1-9-0" in tags_removed
