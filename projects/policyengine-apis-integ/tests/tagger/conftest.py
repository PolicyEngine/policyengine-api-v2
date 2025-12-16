"""Configuration for tagger API integration tests."""

from pydantic_settings import BaseSettings, SettingsConfigDict
import pytest
import httpx


class Settings(BaseSettings):
    """Settings for tagger integration tests."""

    base_url: str = ""
    access_token: str = ""

    model_config = SettingsConfigDict(env_prefix="tagger_integ_test_")


settings = Settings()


# Skip all tagger tests if not configured
pytestmark = pytest.mark.skipif(
    not settings.base_url or not settings.access_token,
    reason="Tagger tests require tagger_integ_test_base_url and tagger_integ_test_access_token",
)


@pytest.fixture()
def tagger_client() -> httpx.Client:
    """HTTP client configured for the tagger API."""
    return httpx.Client(
        base_url=settings.base_url,
        headers={"Authorization": f"Bearer {settings.access_token}"},
        timeout=30.0,
    )
