import httpx
import pytest
from pydantic_settings import BaseSettings, SettingsConfigDict

from policyengine_api_simulation_client import AuthenticatedClient, Client


class Settings(BaseSettings):
    base_url: str = "http://localhost:8082"
    access_token: str | None = None
    timeout_in_millis: int = 600_000  # 10 minutes for full simulations
    poll_interval_seconds: float = 5.0
    us_model_version: str = "1.562.3"

    model_config = SettingsConfigDict(env_prefix="simulation_integ_test_")


settings = Settings()


@pytest.fixture()
def client() -> Client | AuthenticatedClient:
    """Create HTTP client for simulation API."""
    timeout = httpx.Timeout(timeout=settings.timeout_in_millis / 1000)
    if settings.access_token:
        return AuthenticatedClient(
            base_url=settings.base_url, token=settings.access_token, timeout=timeout
        )
    return Client(base_url=settings.base_url, timeout=timeout)


@pytest.fixture()
def us_model_version() -> str:
    """Return the US model version for testing specific version scenarios."""
    return settings.us_model_version


@pytest.fixture()
def poll_interval() -> float:
    """Return poll interval in seconds."""
    return settings.poll_interval_seconds


@pytest.fixture()
def max_wait_seconds() -> float:
    """Return max wait time in seconds."""
    return settings.timeout_in_millis / 1000
