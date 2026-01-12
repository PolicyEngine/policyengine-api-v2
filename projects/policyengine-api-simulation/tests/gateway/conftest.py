"""Pytest fixtures for gateway tests."""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.modal.gateway.endpoints import router


def create_gateway_app() -> FastAPI:
    """Create a FastAPI app with the gateway router for testing."""
    app = FastAPI(
        title="Test PolicyEngine Simulation API",
        description="Test instance for unit tests",
        version="0.0.1",
    )
    app.include_router(router)
    return app


@pytest.fixture
def client() -> TestClient:
    """Create a test client for the gateway API."""
    return TestClient(create_gateway_app())
