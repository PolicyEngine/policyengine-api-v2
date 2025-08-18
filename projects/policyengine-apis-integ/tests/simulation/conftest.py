import policyengine_api_simulation_client
import pytest
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    base_url: str = "http://localhost:8081"
    access_token: str | None = None
    timeout_in_millis: int = 200

    model_config = SettingsConfigDict(env_prefix="simulation_integ_test_")


settings = Settings()


@pytest.fixture()
def client() -> policyengine_api_simulation_client.DefaultApi:
    config = policyengine_api_simulation_client.Configuration(host=settings.base_url)
    client = policyengine_api_simulation_client.ApiClient(config)
    if settings.access_token:
        client.default_headers["Authorization"] = f"Bearer {settings.access_token}"
    return policyengine_api_simulation_client.DefaultApi(client)
