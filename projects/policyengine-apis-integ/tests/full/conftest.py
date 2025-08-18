import policyengine_api_full_client
from pydantic_settings import BaseSettings, SettingsConfigDict
import pytest


class Settings(BaseSettings):
    base_url: str = "http://localhost:8080"
    access_token: str | None = None
    timeout_in_millis: int = 200

    model_config = SettingsConfigDict(env_prefix="full_integ_test_")


settings = Settings()


@pytest.fixture()
def client() -> policyengine_api_full_client.DefaultApi:
    config = policyengine_api_full_client.Configuration(host=settings.base_url)
    client = policyengine_api_full_client.ApiClient(config)
    if settings.access_token:
        client.default_headers["Authorization"] = f"Bearer {settings.access_token}"
    return policyengine_api_full_client.DefaultApi(client)
