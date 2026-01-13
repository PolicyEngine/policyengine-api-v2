from concurrent.futures import ThreadPoolExecutor, as_completed

from policyengine_api_simulation_client import Client, AuthenticatedClient
from policyengine_api_simulation_client.api.default import ping_ping_post
from policyengine_api_simulation_client.models import PingRequest, PingResponse
from policyengine_api_simulation_client.errors import UnexpectedStatus
import backoff
import httpx
import pytest


@backoff.on_exception(
    backoff.expo,
    (httpx.HTTPStatusError, UnexpectedStatus),
    max_tries=5,
    giveup=lambda e: getattr(e, "response", {}).get("status_code", 0) != 503,
)
def test_ping(client: Client | AuthenticatedClient):
    """
    Given a running simulation API
    When a ping request is sent
    Then the response contains the incremented value.
    """
    response = ping_ping_post.sync(client=client, body=PingRequest(value=12))
    assert isinstance(response, PingResponse)
    assert response.incremented == 13


@pytest.mark.beta_only
def test_ping_concurrent_requests(client: Client | AuthenticatedClient):
    """
    Given a running simulation API
    When 10 ping requests are sent simultaneously
    Then all requests return successfully with correct incremented values.
    """
    # Given
    num_requests = 10

    def make_ping_request(
        value: int,
    ) -> tuple[int, PingResponse | None, Exception | None]:
        """Make a single ping request and return (value, response, error)."""
        try:
            response = ping_ping_post.sync(client=client, body=PingRequest(value=value))
            return (value, response, None)
        except Exception as e:
            return (value, None, e)

    # When - send 10 requests simultaneously
    results = []
    with ThreadPoolExecutor(max_workers=num_requests) as executor:
        futures = {
            executor.submit(make_ping_request, i): i for i in range(num_requests)
        }
        for future in as_completed(futures):
            results.append(future.result())

    # Then - all requests should succeed
    errors = [(v, e) for v, r, e in results if e is not None]
    assert len(errors) == 0, f"Some requests failed: {errors}"

    # And - all responses should have correct incremented values
    for value, response, error in results:
        assert isinstance(
            response, PingResponse
        ), f"Request {value} did not return PingResponse"
        assert (
            response.incremented == value + 1
        ), f"Request {value} returned wrong increment: expected {value + 1}, got {response.incremented}"
