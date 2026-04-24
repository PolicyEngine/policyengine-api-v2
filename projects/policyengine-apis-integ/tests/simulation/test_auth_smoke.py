"""Authenticated smoke tests that must pass in both beta and prod.

These tests assert the end-to-end auth wiring is functional: the gateway
has the ``gateway-auth`` Modal secret attached with issuer/audience
configuration, the JWKS-fetch and token verification work against the
configured Auth0 tenant, and the test harness can mint a bearer token
that the gateway accepts.

They intentionally do NOT use ``@pytest.mark.beta_only`` so they run in the
prod deployment job too. Without an auth test in the prod integ suite, a
misconfigured ``gateway-auth`` secret in the ``main`` Modal environment
would pass CI while serving 503s to every real client.
"""

from __future__ import annotations

import httpx
import pytest

from .conftest import settings


pytestmark = pytest.mark.skipif(
    not settings.access_token,
    reason="Auth token not configured; skipping auth smoke tests (dev only).",
)


def _base() -> str:
    return settings.base_url.rstrip("/")


def test_gated_endpoint_rejects_missing_token() -> None:
    """No ``Authorization`` header on a gated endpoint must be rejected.

    Without a token the gateway's ``Depends(require_auth)`` surfaces a 403
    (HTTPBearer auto_error=False + JWTDecoder rejects). A 2xx here means
    the auth dependency is not actually wired and the gateway is open.
    """
    response = httpx.get(
        f"{_base()}/jobs/auth-smoke-probe-no-token",
        timeout=30.0,
    )

    assert response.status_code in (401, 403), (
        f"Expected the gated /jobs endpoint to reject an unauthenticated "
        f"request with 401/403, got {response.status_code}: {response.text[:200]}"
    )


def test_gated_endpoint_accepts_valid_token() -> None:
    """With a valid bearer token the endpoint must advance past auth.

    The probe job id will not resolve, so the expected body is a 404.
    Any auth-layer status (401, 403, 503) means the container's
    ``gateway-auth`` secret is misattached or ``GATEWAY_AUTH_ISSUER`` /
    ``GATEWAY_AUTH_AUDIENCE`` do not match the tenant that minted the
    token — which is exactly the silent-failure mode this test guards.
    """
    response = httpx.get(
        f"{_base()}/jobs/auth-smoke-probe-does-not-exist",
        headers={"Authorization": f"Bearer {settings.access_token}"},
        timeout=30.0,
    )

    auth_failures = {401, 403, 503}
    assert response.status_code not in auth_failures, (
        f"Gated endpoint rejected a valid token with {response.status_code}: "
        f"{response.text[:200]}. Check that the gateway-auth Modal secret "
        f"in the deploy environment matches the Auth0 tenant minting the token."
    )
    assert response.status_code == 404, (
        f"Expected 404 for an unknown job id after auth, got "
        f"{response.status_code}: {response.text[:200]}"
    )
