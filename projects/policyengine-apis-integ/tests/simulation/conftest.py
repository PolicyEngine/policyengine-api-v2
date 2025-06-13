import policyengine_simulation_api_client
import pytest
from pydantic_settings import BaseSettings, SettingsConfigDict
from urllib3.util.retry import Retry
from urllib3 import PoolManager


class Settings(BaseSettings):
    base_url: str = "http://localhost:8081"
    access_token: str | None = None
    timeout_in_millis: int = 200

    model_config = SettingsConfigDict(env_prefix="simulation_integ_test_")


settings = Settings()


@pytest.fixture()
def client() -> policyengine_simulation_api_client.DefaultApi:
    config = policyengine_simulation_api_client.Configuration(host=settings.base_url)

    # Set up retry logic
    retries = Retry(
        total=5,
        backoff_factor=0.5,
        status_forcelist=[503],
        allowed_methods=["HEAD", "GET", "POST", "PUT", "DELETE", "OPTIONS", "TRACE"],
        raise_on_status=False,
    )

    # Construct the ApiClient
    api_client = policyengine_simulation_api_client.ApiClient(configuration=config)

    # Inject the retry logic into the underlying urllib3 pool manager
    api_client.rest_client.pool_manager = PoolManager(
        retries=retries
    )

    if settings.access_token:
        api_client.default_headers["Authorization"] = f"Bearer {settings.access_token}"

    return policyengine_simulation_api_client.DefaultApi(api_client)
