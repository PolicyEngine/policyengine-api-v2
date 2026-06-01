"""
FastAPI endpoints for the Gateway API.
"""

import logging
from typing import Optional

import modal
from fastapi import APIRouter, Depends, HTTPException

from src.modal.budget_window_state import (
    build_batch_status_response,
    create_initial_batch_state,
    get_batch_job_seed,
    get_batch_job_state,
    put_batch_job_seed,
    put_batch_job_state,
)
from src.modal.gateway.auth import require_auth
from src.modal.gateway.errors import log_and_redact_exception
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
from src.modal.gateway.responses import (
    batch_status_response,
    failed_job_response,
    running_job_response,
)
from policyengine_api_simulation.dataset_uri import (
    runtime_dataset_uri,
    select_dataset_revision,
)
from policyengine_api_simulation.hf_dataset import (
    HuggingFaceDatasetReferenceError,
)

logger = logging.getLogger(__name__)

router = APIRouter()
JOB_METADATA_DICT_NAME = "simulation-api-job-metadata"
APP_RELEASE_BUNDLES_DICT_NAME = "simulation-api-app-release-bundles"


def _job_metadata_store():
    return modal.Dict.from_name(JOB_METADATA_DICT_NAME, create_if_missing=True)


def _app_release_bundle_store():
    return modal.Dict.from_name(APP_RELEASE_BUNDLES_DICT_NAME, create_if_missing=True)


def _app_release_bundle(app_name: str) -> dict:
    bundle = _app_release_bundle_store().get(app_name)
    return bundle if isinstance(bundle, dict) else {}


def _split_requested_revision(requested_data: str) -> tuple[str, str | None]:
    if "@" not in requested_data:
        return requested_data, None
    dataset_name, revision = requested_data.rsplit("@", maxsplit=1)
    if not dataset_name or not revision:
        raise ValueError(f"Invalid dataset revision reference: {requested_data}")
    return dataset_name, revision


def _country_bundle_data_version(country_bundle: dict) -> str | None:
    data_version = country_bundle.get("data_version")
    return data_version if isinstance(data_version, str) else None


def _resolve_dataset_uri_from_app_bundle(
    *,
    app_bundle: dict,
    country: str,
    requested_data: str | None,
    requested_data_version: str | None = None,
) -> str | None:
    country_bundle = app_bundle.get(country.lower())

    if requested_data is None:
        if not isinstance(country_bundle, dict):
            return None
        default_uri = country_bundle.get("default_dataset_uri")
        if not isinstance(default_uri, str):
            return None
        return runtime_dataset_uri(
            default_uri,
            default_revision=(
                requested_data_version or _country_bundle_data_version(country_bundle)
            ),
        )

    requested_without_revision, requested_revision = _split_requested_revision(
        requested_data
    )
    revision = select_dataset_revision(
        requested_revision=requested_revision,
        requested_data_version=requested_data_version,
    )
    bundle_data_version = (
        _country_bundle_data_version(country_bundle)
        if isinstance(country_bundle, dict)
        else None
    )

    if "://" in requested_without_revision:
        if requested_without_revision.startswith("hf://"):
            return runtime_dataset_uri(
                requested_without_revision,
                default_revision=revision or bundle_data_version,
            )
        if requested_without_revision.startswith("gs://"):
            return runtime_dataset_uri(
                requested_without_revision,
                default_revision=revision,
            )
        return requested_data

    if not isinstance(country_bundle, dict):
        return requested_data

    aliases = country_bundle.get("dataset_aliases")
    if not isinstance(aliases, dict):
        aliases = {}
    dataset_name = aliases.get(requested_without_revision, requested_without_revision)

    if "://" in dataset_name:
        return runtime_dataset_uri(
            dataset_name,
            default_revision=revision or bundle_data_version,
        )

    dataset_uris = country_bundle.get("dataset_uris")
    if not isinstance(dataset_uris, dict):
        return requested_data
    dataset_uri = dataset_uris.get(dataset_name)
    if not isinstance(dataset_uri, str):
        return requested_data
    return runtime_dataset_uri(
        dataset_uri,
        default_revision=revision or bundle_data_version,
    )


def _modal_exception_class(name: str):
    exception_module = getattr(modal, "exception", None)
    if exception_module is None:
        return None
    return getattr(exception_module, name, None)


def _is_modal_exception(exc: BaseException, name: str) -> bool:
    exception_class = _modal_exception_class(name)
    return exception_class is not None and isinstance(exc, exception_class)


def _is_modal_job_not_found(exc: BaseException) -> bool:
    return _is_modal_exception(exc, "NotFoundError") or _is_modal_exception(
        exc, "OutputExpiredError"
    )


def _build_policyengine_bundle(
    country: str, resolved_version: str, app_name: str, payload: dict
) -> PolicyEngineBundle:
    app_bundle = _app_release_bundle(app_name)
    dataset = payload.get("data")
    data_version = payload.get("data_version")
    resolved_dataset = _resolve_dataset_uri_from_app_bundle(
        app_bundle=app_bundle,
        country=country,
        requested_data=dataset if isinstance(dataset, str) else None,
        requested_data_version=data_version if isinstance(data_version, str) else None,
    )
    return PolicyEngineBundle(
        model_version=resolved_version,
        data_version=data_version,
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


def _build_budget_window_parent_payload(
    request: BudgetWindowBatchRequest,
    *,
    resolved_version: str,
    resolved_app_name: str,
    bundle: PolicyEngineBundle,
) -> dict:
    payload = request.model_dump(
        exclude={"telemetry"},
        mode="json",
        exclude_none=True,
    )
    payload["version"] = resolved_version
    if request.telemetry is not None:
        payload["_telemetry"] = request.telemetry.model_dump(mode="json")
    payload["_metadata"] = {
        "resolved_version": resolved_version,
        "resolved_app_name": resolved_app_name,
        "policyengine_bundle": bundle.model_dump(mode="json"),
    }
    return payload


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
    dependencies=[Depends(require_auth)],
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
        exclude_none=True,
    )
    run_id = request.telemetry.run_id if request.telemetry else None
    if request.telemetry is not None:
        payload["_telemetry"] = request.telemetry.model_dump(mode="json")

    try:
        bundle = _build_policyengine_bundle(
            request.country, resolved_version, app_name, payload
        )
    except (ValueError, HuggingFaceDatasetReferenceError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

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
    dependencies=[Depends(require_auth)],
)
async def submit_budget_window_batch(request: BudgetWindowBatchRequest):
    """
    Submit a budget-window batch job.
    """
    try:
        app_name, resolved_version = get_app_name(request.country, request.version)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    try:
        bundle = _build_policyengine_bundle(
            request.country,
            resolved_version,
            app_name,
            request.model_dump(mode="json"),
        )
    except (ValueError, HuggingFaceDatasetReferenceError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    payload = _build_budget_window_parent_payload(
        request,
        resolved_version=resolved_version,
        resolved_app_name=app_name,
        bundle=bundle,
    )

    batch_func = modal.Function.from_name(app_name, "run_budget_window_batch")
    call = batch_func.spawn(payload)
    batch_job_id = call.object_id

    seed_state = create_initial_batch_state(
        batch_job_id=batch_job_id,
        request=request,
        resolved_version=resolved_version,
        resolved_app_name=app_name,
        bundle=bundle,
    )
    put_batch_job_seed(seed_state)

    return BudgetWindowBatchSubmitResponse(
        batch_job_id=batch_job_id,
        status=seed_state.status,
        poll_url=f"/budget-window-jobs/{batch_job_id}",
        country=request.country,
        version=resolved_version,
        resolved_app_name=app_name,
        policyengine_bundle=bundle,
        run_id=seed_state.run_id,
    )


@router.get(
    "/jobs/{job_id}",
    response_model=JobStatusResponse,
    response_model_exclude_none=True,
    dependencies=[Depends(require_auth)],
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
    job_metadata = _job_metadata_store().get(job_id)
    if job_metadata is None:
        raise HTTPException(status_code=404, detail=f"Job not found: {job_id}")

    try:
        call = modal.FunctionCall.from_id(job_id)
    except Exception as exc:
        if _is_modal_job_not_found(exc):
            raise HTTPException(status_code=404, detail=f"Job not found: {job_id}")
        raise

    try:
        result = call.get(timeout=0)
        return JobStatusResponse(
            status="complete", result=result, **(job_metadata or {})
        )
    except TimeoutError:
        return running_job_response(job_metadata)
    except Exception as exc:
        if _is_modal_job_not_found(exc):
            raise HTTPException(status_code=404, detail=f"Job not found: {job_id}")
        redacted = log_and_redact_exception(
            exc,
            scope="simulation_job_status",
            context={"job_id": job_id},
        )
        return failed_job_response(error=redacted, job_metadata=job_metadata)


@router.get(
    "/budget-window-jobs/{batch_job_id}",
    response_model=BudgetWindowBatchStatusResponse,
    response_model_exclude_none=True,
    dependencies=[Depends(require_auth)],
)
async def get_budget_window_job_status(batch_job_id: str):
    """
    Poll for budget-window batch status.
    """
    state = get_batch_job_state(batch_job_id)
    if state is not None:
        return batch_status_response(build_batch_status_response(state))

    seed_state = get_batch_job_seed(batch_job_id)
    if seed_state is None:
        raise HTTPException(
            status_code=404, detail=f"Budget-window job not found: {batch_job_id}"
        )

    try:
        call = modal.FunctionCall.from_id(batch_job_id)
    except Exception:
        return batch_status_response(build_batch_status_response(seed_state))

    try:
        result = call.get(timeout=0)
    except TimeoutError:
        return batch_status_response(build_batch_status_response(seed_state))
    except Exception as exc:
        # Persist the failure so subsequent polls don't resurrect the
        # "submitted" status from the seed store (#448). We deliberately
        # overwrite the main job store entry as well as the seed so either
        # lookup path observes the terminal failed state.
        redacted = log_and_redact_exception(
            exc,
            scope="budget_window_parent_call",
            context={"batch_job_id": batch_job_id},
        )
        seed_state.status = "failed"
        seed_state.error = redacted
        put_batch_job_state(seed_state)
        put_batch_job_seed(seed_state)
        return batch_status_response(build_batch_status_response(seed_state))

    response = BudgetWindowBatchStatusResponse.model_validate(result)
    return batch_status_response(response)


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
