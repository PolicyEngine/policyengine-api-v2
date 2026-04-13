from __future__ import annotations

from datetime import UTC, datetime

from fastapi import FastAPI
from fastapi.testclient import TestClient

from policyengine_api_simulation.internal_observability.contracts import (
    InternalObservabilityBackendCapability,
    InternalObservabilityBackendHealth,
    InternalObservabilityCapabilitiesResponse,
    InternalObservabilityHealthResponse,
)
from policyengine_api_simulation.internal_observability.router import (
    create_router,
)
from policyengine_api_simulation.internal_observability.service import (
    get_internal_observability_query_service,
)
from policyengine_api_simulation.settings import get_settings


class FakeQueryService:
    def get_health(self) -> InternalObservabilityHealthResponse:
        return InternalObservabilityHealthResponse(
            status="ok",
            backends=[
                InternalObservabilityBackendHealth(
                    backend="loki",
                    configured=True,
                    reachable=True,
                    checked_at=datetime(2026, 4, 11, tzinfo=UTC),
                    detail="HTTP 200",
                )
            ],
        )

    def get_capabilities(self) -> InternalObservabilityCapabilitiesResponse:
        return InternalObservabilityCapabilitiesResponse(
            auth_scheme="bearer_token",
            backends=[
                InternalObservabilityBackendCapability(
                    backend="loki",
                    configured=True,
                    operations=["ready", "query_logs"],
                )
            ],
            routes=[],
        )


def create_app() -> FastAPI:
    app = FastAPI()
    app.include_router(create_router())
    app.dependency_overrides[get_internal_observability_query_service] = (
        lambda: FakeQueryService()
    )
    return app


def test_internal_observability_router__rejects_missing_or_invalid_token(monkeypatch):
    monkeypatch.setenv("OBSERVABILITY_INTERNAL_API_TOKEN", "secret-token")
    get_settings.cache_clear()
    client = TestClient(create_app())
    try:
        missing = client.get("/internal/observability/health")
        invalid = client.get(
            "/internal/observability/health",
            headers={"Authorization": "Bearer wrong-token"},
        )
    finally:
        client.close()
        get_settings.cache_clear()

    assert missing.status_code == 401
    assert invalid.status_code == 401


def test_internal_observability_router__rejects_when_token_not_configured():
    get_settings.cache_clear()
    client = TestClient(create_app())
    try:
        response = client.get(
            "/internal/observability/health",
            headers={"Authorization": "Bearer anything"},
        )
    finally:
        client.close()
        get_settings.cache_clear()

    assert response.status_code == 503
    assert "not configured" in response.json()["detail"]


def test_internal_observability_router__returns_health_and_capabilities(monkeypatch):
    monkeypatch.setenv("OBSERVABILITY_INTERNAL_API_TOKEN", "secret-token")
    get_settings.cache_clear()
    client = TestClient(create_app())
    headers = {"Authorization": "Bearer secret-token"}
    try:
        health = client.get("/internal/observability/health", headers=headers)
        capabilities = client.get(
            "/internal/observability/capabilities",
            headers=headers,
        )
    finally:
        client.close()
        get_settings.cache_clear()

    assert health.status_code == 200
    assert health.json()["status"] == "ok"
    assert capabilities.status_code == 200
    assert capabilities.json()["auth_scheme"] == "bearer_token"
    assert capabilities.json()["backends"][0]["backend"] == "loki"


def test_internal_observability_router__exposes_expected_openapi_paths(monkeypatch):
    monkeypatch.setenv("OBSERVABILITY_INTERNAL_API_TOKEN", "secret-token")
    get_settings.cache_clear()
    app = create_app()
    try:
        openapi_schema = app.openapi()
    finally:
        get_settings.cache_clear()

    assert "/internal/observability/health" in openapi_schema["paths"]
    assert "/internal/observability/capabilities" in openapi_schema["paths"]
