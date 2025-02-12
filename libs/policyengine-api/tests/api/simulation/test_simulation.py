# libs/policyengine-api/tests/api/simulation/test_simulation.py

import json
import pytest
from fastapi.testclient import TestClient
from sqlmodel import SQLModel, Session
from policyengine_api.simulation.router import create_simulation_router
from policyengine_api.simulation.models import SimulationJob
from policyengine_fastapi.database import (
    create_sqlite_engine,
    create_session_dep,
)
from policyengine_fastapi.auth.jwt_decoder import JWTDecoder


# Helper to create a minimal FastAPI app for testing a router
def createApi(router):
    from fastapi import FastAPI

    app = FastAPI()
    app.include_router(router)
    return app


@pytest.fixture
def client():
    # Create an in-memory SQLite engine and re-create all tables.
    engine = create_sqlite_engine()
    SQLModel.metadata.drop_all(engine)
    SQLModel.metadata.create_all(engine)

    # Create dummy auth decoders; for testing we use simple ones.
    auth = JWTDecoder(
        issuer="test_issuer", audience="test_audience", auto_error=True
    )
    optional_auth = JWTDecoder(
        issuer="test_issuer", audience="test_audience", auto_error=False
    )

    # Create the session dependency using the test engine.
    session_dep = create_session_dep(engine)

    # Create the simulation router with the dependencies.
    router = create_simulation_router(
        session_dependency=session_dep, optional_auth=optional_auth, auth=auth
    )

    api = createApi(router)
    return TestClient(api), engine


def test_run_simulation(monkeypatch, client):
    test_client, engine = client

    # Define the test input:
    test_input = {"scope": "macro", "country": "us", "reform": {}}
    input_json = json.dumps(test_input)

    # Insert a simulation job into the database with the input data.
    with Session(engine) as session:
        job = SimulationJob(input_data=input_json, status="pending")
        session.add(job)
        session.commit()
        session.refresh(job)
        job_id = job.id

    # Patch the Simulation.calculate method so that it returns a predictable result.
    # This avoids calling the real simulation logic during testing.
    def fake_calculate(self):
        return {"simulated": True}

    monkeypatch.setattr("policyengine.Simulation.calculate", fake_calculate)

    # Provide a dummy valid auth token.
    # Adjust the token format if your JWTDecoder expects a different structure.
    token_value = '{"sub": "test"}'
    headers = {"Authorization": f"Bearer {token_value}"}

    # Call the endpoint to run the simulation synchronously.
    response = test_client.post(f"/simulation/{job_id}/run", headers=headers)
    assert response.status_code == 200, response.text

    # Verify that the returned job has been updated.
    result = response.json()
    assert (
        result["status"] == "complete"
    ), f"Expected status 'complete', got {result['status']}"

    # Check that output_data contains the simulated result.
    output_data = json.loads(result["output_data"])
    assert output_data == {
        "simulated": True
    }, f"Unexpected simulation result: {output_data}"
