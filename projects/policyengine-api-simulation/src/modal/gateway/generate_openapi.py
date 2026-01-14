"""
Generate OpenAPI spec for the Modal Gateway API.

This creates a FastAPI app with the same route signatures as the gateway
but without Modal dependencies, allowing OpenAPI generation without credentials.

Usage:
    cd projects/policyengine-api-simulation
    uv run python -m src.modal.gateway.generate_openapi
"""

import json
from pathlib import Path
from typing import Optional

from fastapi import FastAPI
from fastapi.responses import JSONResponse

from src.modal.gateway.models import (
    JobStatusResponse,
    JobSubmitResponse,
    PingRequest,
    PingResponse,
    SimulationRequest,
)


def create_openapi_app() -> FastAPI:
    """Create FastAPI app for OpenAPI generation."""
    app = FastAPI(
        title="PolicyEngine Simulation Gateway API",
        description="Submit and poll simulation jobs on Modal",
        version="1.0.0",
    )

    @app.post(
        "/simulate/economy/comparison",
        response_model=JobSubmitResponse,
        responses={
            200: {"description": "Job submitted successfully"},
            400: {"description": "Invalid request (unknown country/version)"},
        },
    )
    async def submit_simulation(request: SimulationRequest) -> JobSubmitResponse:
        """
        Submit a simulation job.

        Routes to the appropriate simulation app based on country and version.
        Returns immediately with a job_id for polling.
        """
        raise NotImplementedError("Stub for OpenAPI generation")

    @app.get(
        "/jobs/{job_id}",
        response_model=JobStatusResponse,
        responses={
            200: {"description": "Job complete", "model": JobStatusResponse},
            202: {"description": "Job still running"},
            404: {"description": "Job not found"},
            500: {"description": "Job failed"},
        },
    )
    async def get_job_status(job_id: str) -> JobStatusResponse:
        """
        Poll for job status.

        Returns:
            - 200 with status="complete" and result when done
            - 202 with status="running" while in progress
            - 404 if job_id not found
            - 500 with status="failed" and error on failure
        """
        raise NotImplementedError("Stub for OpenAPI generation")

    @app.get("/versions")
    async def list_versions() -> dict:
        """List all available versions for all countries."""
        raise NotImplementedError("Stub for OpenAPI generation")

    @app.get("/versions/{country}")
    async def get_country_versions(country: str) -> dict:
        """Get available versions for a specific country."""
        raise NotImplementedError("Stub for OpenAPI generation")

    @app.get("/health")
    async def health() -> dict:
        """Health check endpoint."""
        return {"status": "healthy"}

    @app.post("/ping", response_model=PingResponse)
    async def ping(request: PingRequest) -> PingResponse:
        """Verify the API is able to receive and process requests."""
        raise NotImplementedError("Stub for OpenAPI generation")

    return app


def main():
    """Generate OpenAPI spec and write to artifacts."""
    app = create_openapi_app()
    openapi_spec = app.openapi()

    output_path = (
        Path(__file__).parent.parent.parent.parent / "artifacts" / "openapi.json"
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, "w") as f:
        json.dump(openapi_spec, f, indent=2)

    print(f"OpenAPI spec written to {output_path}")


if __name__ == "__main__":
    main()
