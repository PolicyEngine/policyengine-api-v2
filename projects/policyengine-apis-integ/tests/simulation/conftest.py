import policyengine_simulation_api_client
import pytest
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    base_url: str = "http://localhost:8081"
    access_token: str | None = None
    timeout_in_millis: int = 200

    model_config = SettingsConfigDict(env_prefix="simulation_integ_test_")


settings = Settings()


@pytest.fixture()
def client() -> policyengine_simulation_api_client.DefaultApi:
    config = policyengine_simulation_api_client.Configuration(host=settings.base_url)
    client = policyengine_simulation_api_client.ApiClient(config)
    if settings.access_token:
        client.default_headers["Authorization"] = f"Bearer {settings.access_token}"
    return policyengine_simulation_api_client.DefaultApi(client)
