"""Helpers for budget-window batch job state."""

from __future__ import annotations

from datetime import UTC, datetime

import modal

from src.modal.gateway.models import (
    BudgetWindowBatchRequest,
    BudgetWindowBatchState,
    BudgetWindowBatchStatusResponse,
    PolicyEngineBundle,
)

BUDGET_WINDOW_JOB_DICT_NAME = "simulation-api-budget-window-jobs"


def _budget_window_job_store():
    return modal.Dict.from_name(BUDGET_WINDOW_JOB_DICT_NAME, create_if_missing=True)


def _utc_now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _build_years(start_year: str, window_size: int) -> list[str]:
    base_year = int(start_year)
    return [str(base_year + offset) for offset in range(window_size)]


def create_initial_batch_state(
    *,
    batch_job_id: str,
    request: BudgetWindowBatchRequest,
    resolved_version: str,
    resolved_app_name: str,
    bundle: PolicyEngineBundle,
) -> BudgetWindowBatchState:
    years = _build_years(request.start_year, request.window_size)
    now = _utc_now_iso()

    return BudgetWindowBatchState(
        batch_job_id=batch_job_id,
        status="submitted",
        country=request.country,
        version=resolved_version,
        resolved_app_name=resolved_app_name,
        policyengine_bundle=bundle,
        start_year=request.start_year,
        window_size=request.window_size,
        max_parallel=request.max_parallel,
        years=years,
        queued_years=list(years),
        running_years=[],
        completed_years=[],
        failed_years=[],
        child_jobs={},
        partial_annual_impacts={},
        result=None,
        error=None,
        created_at=now,
        updated_at=now,
        run_id=request.telemetry.run_id if request.telemetry else None,
    )


def get_batch_job_state(batch_job_id: str) -> BudgetWindowBatchState | None:
    payload = _budget_window_job_store().get(batch_job_id)
    if payload is None:
        return None
    return BudgetWindowBatchState.model_validate(payload)


def put_batch_job_state(state: BudgetWindowBatchState) -> None:
    serialized = state.model_dump(mode="json")
    _budget_window_job_store()[state.batch_job_id] = serialized


def build_batch_status_response(
    state: BudgetWindowBatchState,
) -> BudgetWindowBatchStatusResponse:
    total_years = len(state.years)
    progress = (
        0 if total_years == 0 else round(len(state.completed_years) / total_years * 100)
    )

    return BudgetWindowBatchStatusResponse(
        status=state.status,
        progress=progress,
        completed_years=state.completed_years,
        running_years=state.running_years,
        queued_years=state.queued_years,
        failed_years=state.failed_years,
        child_jobs=state.child_jobs,
        result=state.result,
        error=state.error,
        resolved_app_name=state.resolved_app_name,
        policyengine_bundle=state.policyengine_bundle,
        run_id=state.run_id,
    )
