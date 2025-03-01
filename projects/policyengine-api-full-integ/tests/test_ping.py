from httpx import Timeout
from policyengine_api_full_client import Client
from policyengine_api_full_client.api.default import ping_ping_post
from policyengine_api_full_client.models.ping_request import PingRequest
from policyengine_api_full_client.models.http_validation_error import HTTPValidationError
from pydantic_settings import BaseSettings, SettingsConfigDict
import pytest

class Settings(BaseSettings):
    base_url:str = "http://localhost:8000"
    timeout_in_millis:int = 200

    model_config = SettingsConfigDict(env_prefix='integ_test_')

settings = Settings()

@pytest.fixture()
def client():
    return Client(base_url=settings.base_url, timeout=Timeout(settings.timeout_in_millis/1000.0))


# I don't love this client. We should investigate alternatives.
# the package structure is really tedious to use
# it doesn't define methods on the client so it's not very OO
# and it returns a union instead of just throwing an exception
def test_ping(client:Client):
    response = ping_ping_post.sync(client=client, body=PingRequest(value=12))
    assert response != None
    assert not isinstance(response, HTTPValidationError)
    assert response.incremented == 13