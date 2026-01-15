"""
FastAPI endpoints for the Gateway API.
"""

import logging
from typing import Optional

import modal
from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse

from src.modal.gateway.models import (
    JobStatusResponse,
    JobSubmitResponse,
    PingRequest,
    PingResponse,
    SimulationRequest,
)

logger = logging.getLogger(__name__)

router = APIRouter()


def get_app_name(country: str, version: Optional[str]) -> tuple[str, str]:
    """
    Resolve country + version to Modal app name.

    Returns:
        Tuple of (app_name, resolved_version)
    """
    country_lower = country.lower()
    if country_lower not in ("us", "uk"):
        raise ValueError(f"Unknown country: {country}")

    version_dict = modal.Dict.from_name(f"simulation-api-{country_lower}-versions")

    # Resolve version
    if version is None:
        resolved_version = version_dict["latest"]
    else:
        resolved_version = version

    # Get app name for this version
    try:
        app_name = version_dict[resolved_version]
    except KeyError:
        raise ValueError(f"Unknown version {resolved_version} for country {country}")

    return app_name, resolved_version


NATIONAL_WITH_BREAKDOWNS = "national-with-breakdowns"
NATIONAL_WITH_BREAKDOWNS_TEST = "national-with-breakdowns-test"


@router.post("/simulate/economy/comparison", response_model=JobSubmitResponse)
async def submit_simulation(request: SimulationRequest):
    """
    Submit a simulation job.

    Matches the existing Cloud Run API endpoint path.
    Routes to the appropriate app based on country and version params.
    Returns immediately with job_id for polling.

    Special handling for data="national-with-breakdowns":
    - Only supported for country="us"
    - Spawns 52 parallel simulations (1 national + 51 states)
    - Returns aggregated results with congressional district breakdowns

    Special handling for data="national-with-breakdowns-test":
    - Only supported for country="us"
    - Spawns 11 parallel simulations (1 national + 10 test states)
    - Returns aggregated results with congressional district breakdowns
    """
    try:
        app_name, resolved_version = get_app_name(request.country, request.version)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # Check for national-with-breakdowns special cases
    payload = request.model_dump(exclude={"version"})
    data_value = payload.get("data")
    is_national_breakdowns = data_value in (
        NATIONAL_WITH_BREAKDOWNS,
        NATIONAL_WITH_BREAKDOWNS_TEST,
    )

    if is_national_breakdowns:
        if request.country.lower() != "us":
            raise HTTPException(
                status_code=400,
                detail="national-with-breakdowns is only supported for country='us'",
            )

        # Add test_mode flag to payload for orchestration to use
        if data_value == NATIONAL_WITH_BREAKDOWNS_TEST:
            payload["_test_mode"] = True
            logger.info(
                f"Routing {request.country}:{resolved_version} to {app_name} "
                f"(national-with-breakdowns-test orchestration - 10 states)"
            )
        else:
            logger.info(
                f"Routing {request.country}:{resolved_version} to {app_name} "
                f"(national-with-breakdowns orchestration - all states)"
            )

        func_name = "run_national_with_breakdowns"
    else:
        logger.info(f"Routing {request.country}:{resolved_version} to app {app_name}")
        func_name = "run_simulation"

    # Get function reference from the target app
    sim_func = modal.Function.from_name(app_name, func_name)

    # Spawn the job (returns immediately)
    call = sim_func.spawn(payload)

    return JobSubmitResponse(
        job_id=call.object_id,
        status="submitted",
        poll_url=f"/jobs/{call.object_id}",
        country=request.country,
        version=resolved_version,
    )


@router.get("/jobs/{job_id}")
async def get_job_status(job_id: str):
    """
    Poll for job status.

    Returns:
        - 200 with status="complete" and result when done
        - 202 with status="running" while in progress
        - 500 with status="failed" and error on failure
        - 404 if job_id not found
    """
    try:
        call = modal.FunctionCall.from_id(job_id)
    except Exception:
        raise HTTPException(status_code=404, detail=f"Job not found: {job_id}")

    try:
        result = call.get(timeout=0)
        return JobStatusResponse(status="complete", result=result)
    except TimeoutError:
        return JSONResponse(
            status_code=202,
            content={"status": "running", "result": None, "error": None},
        )
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"status": "failed", "result": None, "error": str(e)},
        )


@router.get("/versions")
async def list_versions():
    """List all available versions for all countries."""
    us_dict = modal.Dict.from_name("simulation-api-us-versions")
    uk_dict = modal.Dict.from_name("simulation-api-uk-versions")

    return {
        "us": dict(us_dict),
        "uk": dict(uk_dict),
    }


@router.get("/versions/{country}")
async def get_country_versions(country: str):
    """Get available versions for a specific country."""
    country_lower = country.lower()
    if country_lower not in ("us", "uk"):
        raise HTTPException(status_code=404, detail=f"Unknown country: {country}")

    version_dict = modal.Dict.from_name(f"simulation-api-{country_lower}-versions")
    return dict(version_dict)


@router.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "healthy"}


@router.post("/ping", response_model=PingResponse)
async def ping(request: PingRequest) -> PingResponse:
    """
    Verify the API is able to receive and process requests.
    Matches the policyengine_fastapi.ping endpoint for test compatibility.
    """
    return PingResponse(incremented=request.value + 1)
