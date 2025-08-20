from fastapi.testclient import TestClient
from policyengine_fastapi.health import (
    HealthRegistry,
    HealthSystemReporter,
    ProbeStatus,
)
import pytest


def test_when_healthy__success_response(
    client: TestClient, health_registry: HealthRegistry
):
    health_registry.register(
        HealthSystemReporter(
            name="test_system",
            probes={"check1": lambda: ProbeStatus(name="check1", healthy=True)},
        )
    )
    response = client.get("/ping/alive")

    assert response.json() == {
        "healthy": True,
        "systems": [
            {
                "name": "test_system",
                "healthy": True,
                "detail": [{"name": "check1", "healthy": True}],
            }
        ],
    }

    assert response.status_code == 200


def test_when_unhealthy_probe___generates_503(
    client: TestClient, health_registry: HealthRegistry
):
    health_registry.register(
        HealthSystemReporter(
            name="test_system",
            probes={
                "check1": lambda: ProbeStatus(name="check1", healthy=True),
                "check2": lambda: ProbeStatus(name="check2", healthy=False),
            },
        )
    )
    response = client.get("/ping/alive")

    assert response.json() == {
        "healthy": False,
        "systems": [
            {
                "name": "test_system",
                "healthy": False,
                "detail": [
                    {"name": "check1", "healthy": True},
                    {"name": "check2", "healthy": False},
                ],
            }
        ],
    }

    assert response.status_code == 503
