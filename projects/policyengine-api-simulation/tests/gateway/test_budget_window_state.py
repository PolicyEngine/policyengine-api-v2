"""Tests for budget-window batch state helpers."""

from src.modal.budget_window_state import (
    build_batch_status_response,
    create_initial_batch_state,
    get_batch_job_state,
    put_batch_job_state,
)
from src.modal.gateway.models import BudgetWindowBatchRequest, PolicyEngineBundle


def test_create_initial_batch_state_builds_queued_years_and_run_id():
    request = BudgetWindowBatchRequest(
        country="us",
        region="us",
        start_year="2026",
        window_size=3,
        max_parallel=2,
        dataset="enhanced_cps_2024",
        scope="macro",
        reform={},
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
    assert state.region == "us"
    assert state.target == "general"
    assert state.years == ["2026", "2027", "2028"]
    assert state.queued_years == ["2026", "2027", "2028"]
    assert state.request_payload["dataset"] == "enhanced_cps_2024"
    assert state.request_payload["scope"] == "macro"
    assert state.request_payload["reform"] == {}
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


def test_batch_state_round_trips_through_modal_dict(mock_modal):
    request = BudgetWindowBatchRequest(
        country="us",
        region="state/ca",
        start_year="2026",
        window_size=2,
        max_parallel=2,
        scope="macro",
        reform={"foo": True},
    )

    state = create_initial_batch_state(
        batch_job_id="fc-parent-123",
        request=request,
        resolved_version="1.500.0",
        resolved_app_name="policyengine-simulation-us1-500-0-uk2-66-0",
        bundle=PolicyEngineBundle(model_version="1.500.0"),
    )
    put_batch_job_state(state)

    restored = get_batch_job_state("fc-parent-123")

    assert restored is not None
    assert restored.region == "state/ca"
    assert restored.target == "general"
    assert restored.request_payload["scope"] == "macro"
    assert restored.request_payload["reform"] == {"foo": True}
