"""
FastAPI endpoints for the Gateway API.
"""

import logging
from time import perf_counter
from typing import Optional

import modal
from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse

from src.modal.gateway.models import (
    JobStatusResponse,
    JobSubmitResponse,
    PingRequest,
    PingResponse,
    PolicyEngineBundle,
    SimulationRequest,
)
from src.modal.observability import (
    build_lifecycle_event,
    build_metric_attributes,
    duration_since_requested_at,
    get_observability,
)

logger = logging.getLogger(__name__)
observability = get_observability("policyengine-simulation-gateway")

router = APIRouter()
JOB_METADATA_DICT_NAME = "simulation-api-job-metadata"
JOB_TELEMETRY_DICT_NAME = "simulation-api-job-telemetry"
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


def get_job_telemetry_registry():
    return modal.Dict.from_name(JOB_TELEMETRY_DICT_NAME, create_if_missing=True)


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


def _build_status_metadata(job_id: str) -> tuple[dict, dict | None]:
    job_metadata = dict(_job_metadata_store().get(job_id) or {})
    telemetry = None
    try:
        telemetry = dict(get_job_telemetry_registry().get(job_id) or {})
    except Exception:
        telemetry = None

    if (
        "run_id" not in job_metadata
        and telemetry is not None
        and telemetry.get("run_id") is not None
    ):
        job_metadata["run_id"] = telemetry["run_id"]
    return job_metadata, telemetry


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

    if version is None:
        resolved_version = version_dict["latest"]
    else:
        resolved_version = version

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
    request_start = perf_counter()
    telemetry_payload = (
        request.telemetry.model_dump(mode="json") if request.telemetry else None
    )
    parent_traceparent = (
        None if request.telemetry is None else request.telemetry.traceparent
    )

    with observability.span(
        "gateway.submit_simulation",
        build_metric_attributes(
            telemetry_payload,
            service="policyengine-simulation-gateway",
            country=request.country,
        ),
        parent_traceparent=parent_traceparent,
    ) as span:
        current_traceparent = span.get_traceparent() or parent_traceparent
        if telemetry_payload is not None and current_traceparent:
            telemetry_payload["traceparent"] = current_traceparent

        observability.emit_lifecycle_event(
            build_lifecycle_event(
                stage="gateway.received",
                status="received",
                service="policyengine-simulation-gateway",
                telemetry=telemetry_payload,
                country=request.country,
            )
        )

        try:
            app_name, resolved_version = get_app_name(request.country, request.version)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))

        payload = request.model_dump(
            exclude={"version", "telemetry"},
            mode="json",
        )
        run_id = None if telemetry_payload is None else telemetry_payload.get("run_id")
        if request.telemetry is not None:
            payload["_telemetry"] = {
                **request.telemetry.model_dump(mode="json"),
                "traceparent": current_traceparent,
            }
            telemetry_payload = payload["_telemetry"]
            run_id = telemetry_payload.get("run_id")

        observability.emit_lifecycle_event(
            build_lifecycle_event(
                stage="gateway.version_resolved",
                status="ok",
                service="policyengine-simulation-gateway",
                telemetry=telemetry_payload,
                country=request.country,
                country_package_version=resolved_version,
                modal_app_name=app_name,
                details={"version": resolved_version},
            )
        )

        logger.info(
            "Routing %s:%s to app %s (run_id=%s)",
            request.country,
            resolved_version,
            app_name,
            run_id,
        )

        sim_func = modal.Function.from_name(app_name, "run_simulation")
        call = sim_func.spawn(payload)

        bundle = _build_policyengine_bundle(request.country, resolved_version, payload)
        _job_metadata_store()[call.object_id] = _serialize_job_metadata(
            app_name,
            bundle,
            run_id,
        )

        registry_payload = dict(telemetry_payload or {})
        registry_payload.update(
            {
                "job_id": call.object_id,
                "country": request.country,
                "country_package_version": resolved_version,
                "modal_app_name": app_name,
            }
        )
        get_job_telemetry_registry()[call.object_id] = registry_payload

        observability.emit_counter(
            "policyengine.simulation.run.count",
            attributes=build_metric_attributes(
                registry_payload,
                service="policyengine-simulation-gateway",
                status="submitted",
            ),
        )
        observability.emit_lifecycle_event(
            build_lifecycle_event(
                stage="gateway.spawned",
                status="submitted",
                service="policyengine-simulation-gateway",
                telemetry=registry_payload,
                duration_seconds=perf_counter() - request_start,
                details={"job_id": call.object_id},
            )
        )

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
    job_metadata, telemetry = _build_status_metadata(job_id)

    with observability.span(
        "gateway.get_job_status",
        build_metric_attributes(
            telemetry,
            service="policyengine-simulation-gateway",
        ),
        parent_traceparent=None if telemetry is None else telemetry.get("traceparent"),
    ) as span:
        current_traceparent = span.get_traceparent()
        if telemetry is not None and current_traceparent:
            telemetry["traceparent"] = current_traceparent

        observability.emit_lifecycle_event(
            build_lifecycle_event(
                stage="result.polled",
                status="polling",
                service="policyengine-simulation-gateway",
                telemetry=telemetry,
                job_id=job_id,
            )
        )

        try:
            call = modal.FunctionCall.from_id(job_id)
        except Exception:
            raise HTTPException(status_code=404, detail=f"Job not found: {job_id}")

        try:
            result = call.get(timeout=0)
            duration = duration_since_requested_at(telemetry)
            observability.emit_lifecycle_event(
                build_lifecycle_event(
                    stage="result.returned",
                    status="complete",
                    service="policyengine-simulation-gateway",
                    telemetry=telemetry,
                    job_id=job_id,
                    duration_seconds=duration,
                )
            )
            if duration is not None:
                observability.emit_histogram(
                    "policyengine.simulation.run.duration.seconds",
                    duration,
                    attributes=build_metric_attributes(
                        telemetry,
                        service="policyengine-simulation-gateway",
                        status="complete",
                    ),
                )
            return JobStatusResponse(
                status="complete",
                result=result,
                **job_metadata,
            )
        except TimeoutError:
            return JSONResponse(
                status_code=202,
                content={
                    "status": "running",
                    "result": None,
                    "error": None,
                    **job_metadata,
                },
            )
        except Exception as e:
            duration = duration_since_requested_at(telemetry)
            observability.emit_counter(
                "policyengine.simulation.failure.count",
                attributes=build_metric_attributes(
                    telemetry,
                    service="policyengine-simulation-gateway",
                    status="failed",
                ),
            )
            observability.emit_lifecycle_event(
                build_lifecycle_event(
                    stage="result.failed",
                    status="failed",
                    service="policyengine-simulation-gateway",
                    telemetry=telemetry,
                    job_id=job_id,
                    duration_seconds=duration,
                    details={"error": str(e)},
                )
            )
            return JSONResponse(
                status_code=500,
                content={
                    "status": "failed",
                    "result": None,
                    "error": str(e),
                    **job_metadata,
                },
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
