"""Contract tests for the live synchronous simulation FastAPI app."""

from fastapi.testclient import TestClient

from fixtures.test_simulation_api_contracts import CURRENT_SINGLE_YEAR_MACRO_RESULT
from policyengine_api_simulation.main import app


def test_standalone_simulation_openapi_keeps_legacy_schema_names():
    spec = app.openapi()
    route = spec["paths"]["/simulate/economy/comparison"]["post"]

    assert route["requestBody"]["content"]["application/json"]["schema"] == {
        "$ref": "#/components/schemas/SimulationOptions"
    }
    assert route["responses"]["200"]["content"]["application/json"]["schema"] == {
        "$ref": "#/components/schemas/EconomyComparison"
    }
    assert (
        "telemetry"
        not in spec["components"]["schemas"]["SimulationOptions"]["properties"]
    )


def test_standalone_simulation_route_returns_legacy_macro_contract(monkeypatch):
    def fake_run_simulation_impl(params):
        assert params == {"country": "us", "reform": {}}
        return CURRENT_SINGLE_YEAR_MACRO_RESULT

    monkeypatch.setattr(
        "policyengine_api_simulation.simulation.run_simulation_impl",
        fake_run_simulation_impl,
    )

    response = TestClient(app).post(
        "/simulate/economy/comparison",
        json={"country": "us", "reform": {}},
    )

    assert response.status_code == 200
    assert response.json() == CURRENT_SINGLE_YEAR_MACRO_RESULT
