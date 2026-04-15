"""Tests for budget-window batch state helpers."""

from src.modal.budget_window_state import (
    build_batch_status_response,
    create_initial_batch_state,
)
from src.modal.gateway.models import BudgetWindowBatchRequest, PolicyEngineBundle


def test_create_initial_batch_state_builds_queued_years_and_run_id():
    request = BudgetWindowBatchRequest(
        country="us",
        region="us",
        start_year="2026",
        window_size=3,
        max_parallel=2,
        _telemetry={
            "run_id": "batch-run-123",
            "process_id": "proc-123",
            "capture_mode": "disabled",
        },
    )

    state = create_initial_batch_state(
        batch_job_id="fc-parent-123",
        request=request,
        resolved_version="1.500.0",
        resolved_app_name="policyengine-simulation-us1-500-0-uk2-66-0",
        bundle=PolicyEngineBundle(model_version="1.500.0"),
    )

    assert state.batch_job_id == "fc-parent-123"
    assert state.status == "submitted"
    assert state.years == ["2026", "2027", "2028"]
    assert state.queued_years == ["2026", "2027", "2028"]
    assert state.run_id == "batch-run-123"


def test_build_batch_status_response_computes_progress_from_completed_years():
    request = BudgetWindowBatchRequest(
        country="us",
        region="us",
        start_year="2026",
        window_size=4,
    )

    state = create_initial_batch_state(
        batch_job_id="fc-parent-123",
        request=request,
        resolved_version="1.500.0",
        resolved_app_name="policyengine-simulation-us1-500-0-uk2-66-0",
        bundle=PolicyEngineBundle(model_version="1.500.0"),
    )
    state.completed_years = ["2026", "2027"]
    state.running_years = ["2028"]
    state.queued_years = ["2029"]

    response = build_batch_status_response(state)

    assert response.progress == 50
    assert response.completed_years == ["2026", "2027"]
    assert response.running_years == ["2028"]
    assert response.queued_years == ["2029"]
