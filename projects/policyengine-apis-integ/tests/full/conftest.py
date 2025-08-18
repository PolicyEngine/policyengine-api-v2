from policyengine_api_full_client import Client, AuthenticatedClient
from pydantic_settings import BaseSettings, SettingsConfigDict
import pytest
import httpx


class Settings(BaseSettings):
    base_url: str = "http://localhost:8080"
    access_token: str | None = None
    timeout_in_millis: int = 800

    model_config = SettingsConfigDict(env_prefix="full_integ_test_")


settings = Settings()


@pytest.fixture()
def client() -> Client:
    timeout = httpx.Timeout(timeout=settings.timeout_in_millis / 1000)
    if settings.access_token:
        return AuthenticatedClient(
            base_url=settings.base_url, token=settings.access_token, timeout=timeout
        )
    return Client(base_url=settings.base_url, timeout=timeout)
