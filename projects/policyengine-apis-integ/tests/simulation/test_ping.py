from policyengine_api_simulation_client import Client
from policyengine_api_simulation_client.api.default import ping_ping_post
from policyengine_api_simulation_client.models import PingRequest
from policyengine_api_simulation_client.errors import UnexpectedStatus
import backoff
import httpx


@backoff.on_exception(
    backoff.expo,
    (httpx.HTTPStatusError, UnexpectedStatus),
    max_tries=5,
    giveup=lambda e: getattr(e, "response", {}).get("status_code", 0) != 503,
)
def test_ping(client: Client):
    response = ping_ping_post.sync(client=client, body=PingRequest(value=12))
    assert response.incremented == 13
