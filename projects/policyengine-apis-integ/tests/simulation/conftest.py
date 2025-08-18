from policyengine_api_simulation_client import Client, AuthenticatedClient
import pytest
from pydantic_settings import BaseSettings, SettingsConfigDict
import httpx


class Settings(BaseSettings):
    base_url: str = "http://localhost:8081"
    access_token: str | None = None
    timeout_in_millis: int = 120_000

    model_config = SettingsConfigDict(env_prefix="simulation_integ_test_")


settings = Settings()


@pytest.fixture()
def client() -> Client | AuthenticatedClient:
    timeout = httpx.Timeout(timeout=settings.timeout_in_millis / 1000)
    if settings.access_token:
        return AuthenticatedClient(
            base_url=settings.base_url, token=settings.access_token, timeout=timeout
        )
    return Client(base_url=settings.base_url, timeout=timeout)
