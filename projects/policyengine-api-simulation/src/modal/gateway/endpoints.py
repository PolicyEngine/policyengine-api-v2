"""
FastAPI endpoints for the Gateway API.
"""

import logging
from typing import Optional

import modal
from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse

from src.modal.gateway.models import (
    BudgetWindowBatchRequest,
    BudgetWindowBatchStatusResponse,
    BudgetWindowBatchSubmitResponse,
    JobStatusResponse,
    JobSubmitResponse,
    PingRequest,
    PingResponse,
    PolicyEngineBundle,
    SimulationRequest,
)

logger = logging.getLogger(__name__)

router = APIRouter()
JOB_METADATA_DICT_NAME = "simulation-api-job-metadata"
DATASET_URIS = {
    "us": {
        "enhanced_cps": "hf://policyengine/policyengine-us-data/enhanced_cps_2024.h5@1.77.0",
        "enhanced_cps_2024": "hf://policyengine/policyengine-us-data/enhanced_cps_2024.h5@1.77.0",
        "cps": "hf://policyengine/policyengine-us-data/cps_2023.h5@1.77.0",
        "cps_2023": "hf://policyengine/policyengine-us-data/cps_2023.h5@1.77.0",
        "pooled_cps": "hf://policyengine/policyengine-us-data/pooled_3_year_cps_2023.h5@1.77.0",
        "pooled_3_year_cps_2023": "hf://policyengine/policyengine-us-data/pooled_3_year_cps_2023.h5@1.77.0",
    },
    "uk": {
        "enhanced_frs": "hf://policyengine/policyengine-uk-data-private/enhanced_frs_2023_24.h5@1.40.3",
        "enhanced_frs_2023_24": "hf://policyengine/policyengine-uk-data-private/enhanced_frs_2023_24.h5@1.40.3",
        "frs": "hf://policyengine/policyengine-uk-data-private/frs_2023_24.h5@1.40.3",
        "frs_2023_24": "hf://policyengine/policyengine-uk-data-private/frs_2023_24.h5@1.40.3",
    },
}


def _job_metadata_store():
    return modal.Dict.from_name(JOB_METADATA_DICT_NAME, create_if_missing=True)


def _build_policyengine_bundle(
    country: str, resolved_version: str, payload: dict
) -> PolicyEngineBundle:
    dataset = payload.get("data")
    if isinstance(dataset, str) and "://" in dataset:
        resolved_dataset = dataset
    elif isinstance(dataset, str):
        resolved_dataset = DATASET_URIS.get(country.lower(), {}).get(dataset, dataset)
    else:
        resolved_dataset = None
    return PolicyEngineBundle(
        model_version=resolved_version,
        dataset=resolved_dataset,
    )


def _serialize_job_metadata(
    resolved_app_name: str,
    bundle: PolicyEngineBundle,
    run_id: str | None = None,
) -> dict:
    return {
        "resolved_app_name": resolved_app_name,
        "policyengine_bundle": bundle.model_dump(),
        "run_id": run_id,
    }


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


@router.post(
    "/simulate/economy/comparison",
    response_model=JobSubmitResponse,
    response_model_exclude_none=True,
)
async def submit_simulation(request: SimulationRequest):
    """
    Submit a simulation job.

    Matches the existing Cloud Run API endpoint path.
    Routes to the appropriate app based on country and version params.
    Returns immediately with job_id for polling.
    """
    try:
        app_name, resolved_version = get_app_name(request.country, request.version)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    payload = request.model_dump(
        exclude={"version", "telemetry"},
        mode="json",
    )
    run_id = request.telemetry.run_id if request.telemetry else None
    if request.telemetry is not None:
        payload["_telemetry"] = request.telemetry.model_dump(mode="json")

    logger.info(
        "Routing %s:%s to app %s (run_id=%s)",
        request.country,
        resolved_version,
        app_name,
        run_id,
    )

    # Get function reference from the target app
    sim_func = modal.Function.from_name(app_name, "run_simulation")

    # Spawn the job (returns immediately)
    call = sim_func.spawn(payload)

    bundle = _build_policyengine_bundle(request.country, resolved_version, payload)
    job_metadata = _serialize_job_metadata(app_name, bundle, run_id)
    _job_metadata_store()[call.object_id] = job_metadata

    return JobSubmitResponse(
        job_id=call.object_id,
        status="submitted",
        poll_url=f"/jobs/{call.object_id}",
        country=request.country,
        version=resolved_version,
        resolved_app_name=app_name,
        policyengine_bundle=bundle,
        run_id=run_id,
    )


@router.post(
    "/simulate/economy/budget-window",
    response_model=BudgetWindowBatchSubmitResponse,
    response_model_exclude_none=True,
)
async def submit_budget_window_batch(request: BudgetWindowBatchRequest):
    """
    Submit a budget-window batch job.

    This contract-first endpoint is intentionally disabled until the
    orchestration worker lands in the follow-up PR. That keeps the route
    mergeable without falsely claiming that work has started.
    """
    raise HTTPException(
        status_code=501,
        detail="Budget-window batch orchestration is not implemented yet",
    )


@router.get(
    "/jobs/{job_id}",
    response_model=JobStatusResponse,
    response_model_exclude_none=True,
)
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

    job_metadata = _job_metadata_store().get(job_id)

    try:
        result = call.get(timeout=0)
        return JobStatusResponse(
            status="complete", result=result, **(job_metadata or {})
        )
    except TimeoutError:
        return JSONResponse(
            status_code=202,
            content={
                "status": "running",
                "result": None,
                "error": None,
                **(job_metadata or {}),
            },
        )
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={
                "status": "failed",
                "result": None,
                "error": str(e),
                **(job_metadata or {}),
            },
        )


@router.get(
    "/budget-window-jobs/{batch_job_id}",
    response_model=BudgetWindowBatchStatusResponse,
    response_model_exclude_none=True,
)
async def get_budget_window_job_status(batch_job_id: str):
    """
    Poll for budget-window batch status.

    This contract-first endpoint is intentionally disabled until the
    orchestration worker lands in the follow-up PR.
    """
    raise HTTPException(
        status_code=501,
        detail="Budget-window batch orchestration is not implemented yet",
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
