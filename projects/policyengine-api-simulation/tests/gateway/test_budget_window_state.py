"""Tests for budget-window batch state helpers."""

from src.modal.budget_window_state import (
    build_batch_status_response,
    create_initial_batch_state,
    get_batch_job_state,
    mark_batch_complete,
    mark_batch_running,
    mark_child_completed,
    mark_child_failed,
    mark_child_started,
    put_batch_job_state,
)
from src.modal.gateway.models import (
    BudgetWindowAnnualImpact,
    BudgetWindowBatchRequest,
    BudgetWindowResult,
    BudgetWindowTotals,
    PolicyEngineBundle,
)


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


def test_state_transition_helpers_track_completion_path():
    request = BudgetWindowBatchRequest(
        country="us",
        region="us",
        start_year="2026",
        window_size=2,
    )

    state = create_initial_batch_state(
        batch_job_id="fc-parent-123",
        request=request,
        resolved_version="1.500.0",
        resolved_app_name="policyengine-simulation-us1-500-0-uk2-66-0",
        bundle=PolicyEngineBundle(model_version="1.500.0"),
    )

    mark_batch_running(state)
    mark_child_started(state, year="2026", child_job_id="child-2026")
    mark_child_completed(
        state,
        year="2026",
        annual_impact=BudgetWindowAnnualImpact(
            year="2026",
            taxRevenueImpact=10,
            federalTaxRevenueImpact=7,
            stateTaxRevenueImpact=3,
            benefitSpendingImpact=5,
            budgetaryImpact=15,
        ),
    )
    mark_batch_complete(
        state,
        result=BudgetWindowResult(
            startYear="2026",
            endYear="2027",
            windowSize=2,
            annualImpacts=[
                BudgetWindowAnnualImpact(
                    year="2026",
                    taxRevenueImpact=10,
                    federalTaxRevenueImpact=7,
                    stateTaxRevenueImpact=3,
                    benefitSpendingImpact=5,
                    budgetaryImpact=15,
                )
            ],
            totals=BudgetWindowTotals(
                taxRevenueImpact=10,
                federalTaxRevenueImpact=7,
                stateTaxRevenueImpact=3,
                benefitSpendingImpact=5,
                budgetaryImpact=15,
            ),
        ),
    )

    assert state.status == "complete"
    assert state.completed_years == ["2026"]
    assert state.failed_years == []
    assert state.child_jobs["2026"].status == "complete"


def test_state_transition_helpers_track_failed_child():
    request = BudgetWindowBatchRequest(
        country="us",
        region="us",
        start_year="2026",
        window_size=2,
    )

    state = create_initial_batch_state(
        batch_job_id="fc-parent-123",
        request=request,
        resolved_version="1.500.0",
        resolved_app_name="policyengine-simulation-us1-500-0-uk2-66-0",
        bundle=PolicyEngineBundle(model_version="1.500.0"),
    )

    mark_batch_running(state)
    mark_child_started(state, year="2027", child_job_id="child-2027")
    mark_child_failed(state, year="2027", error="boom")

    assert state.status == "running"
    assert state.failed_years == ["2027"]
    assert state.child_jobs["2027"].status == "failed"
