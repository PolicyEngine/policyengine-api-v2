"""Tests for gateway authentication middleware."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from fixtures.gateway.shared import create_gateway_app
from src.modal.gateway import auth as auth_module


GATED_REQUESTS = [
    (
        "post",
        "/simulate/economy/comparison",
        {"country": "us", "scope": "macro", "reform": {}},
    ),
    (
        "post",
        "/simulate/economy/budget-window",
        {
            "country": "us",
            "region": "us",
            "scope": "macro",
            "reform": {},
            "start_year": "2026",
            "window_size": 3,
        },
    ),
    ("get", "/jobs/some-job-id", None),
    ("get", "/budget-window-jobs/some-job-id", None),
]


@pytest.fixture
def unauthenticated_client(monkeypatch) -> TestClient:
    """A client where the real auth dependency is active but no token is
    attached. The underlying JWTDecoder is stubbed to preserve the 403
    contract without making a live JWKS fetch."""

    class FailingDecoder:
        def __call__(self, token):
            from fastapi import HTTPException, status

            if token is None:
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN)
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN)

    monkeypatch.setattr(auth_module, "_get_decoder", lambda: FailingDecoder())
    monkeypatch.delenv(auth_module.GATEWAY_AUTH_DISABLED_ENV, raising=False)
    monkeypatch.setenv(auth_module.GATEWAY_AUTH_ISSUER_ENV, "https://issuer.example/")
    monkeypatch.setenv(auth_module.GATEWAY_AUTH_AUDIENCE_ENV, "aud")

    return TestClient(create_gateway_app(authenticate=False))


@pytest.mark.parametrize("method,path,body", GATED_REQUESTS)
def test__given_no_bearer_token__then_gated_endpoint_returns_403(
    unauthenticated_client, method, path, body
):
    """Missing bearer tokens should be rejected on all private endpoints."""

    if method == "post":
        response = unauthenticated_client.post(path, json=body)
    else:
        response = unauthenticated_client.get(path)

    assert response.status_code == 403


def test__given_auth_disabled_env__then_dependency_returns_none(monkeypatch):
    monkeypatch.setenv(auth_module.GATEWAY_AUTH_DISABLED_ENV, "1")
    assert auth_module.require_auth(token=None) is None


def test__given_auth_misconfigured__then_dependency_raises_503(monkeypatch):
    from fastapi import HTTPException

    monkeypatch.delenv(auth_module.GATEWAY_AUTH_DISABLED_ENV, raising=False)
    monkeypatch.delenv(auth_module.GATEWAY_AUTH_ISSUER_ENV, raising=False)
    monkeypatch.delenv(auth_module.GATEWAY_AUTH_AUDIENCE_ENV, raising=False)

    with pytest.raises(HTTPException) as exc_info:
        auth_module.require_auth(token=None)

    assert exc_info.value.status_code == 503


def test__given_health_endpoint__then_auth_not_required(monkeypatch):
    """Health/ping/versions endpoints remain public by design."""

    from fixtures.gateway.shared import create_gateway_app

    client = TestClient(create_gateway_app(authenticate=False))
    response = client.get("/health")
    assert response.status_code == 200
