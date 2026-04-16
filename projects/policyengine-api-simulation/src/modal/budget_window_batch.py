"""Budget-window batch orchestration for versioned simulation apps."""

from __future__ import annotations

import time
from typing import Any

import modal

from src.modal.budget_window_state import (
    build_batch_status_response,
    create_initial_batch_state,
    get_batch_job_seed,
    mark_batch_complete,
    mark_batch_failed,
    mark_batch_running,
    mark_child_completed,
    mark_child_failed,
    mark_child_started,
    put_batch_job_seed,
    put_batch_job_state,
)
from src.modal.gateway.models import (
    BudgetWindowAnnualImpact,
    BudgetWindowBatchRequest,
    BudgetWindowResult,
    BudgetWindowTotals,
    PolicyEngineBundle,
)

POLL_INTERVAL_SECONDS = 0.1


def _extract_request_and_metadata(
    params: dict[str, Any],
) -> tuple[BudgetWindowBatchRequest, str, str, PolicyEngineBundle]:
    request = BudgetWindowBatchRequest.model_validate(params)
    metadata = params.get("_metadata")
    if not isinstance(metadata, dict):
        raise ValueError("Missing internal batch metadata")

    resolved_app_name = metadata.get("resolved_app_name")
    resolved_version = metadata.get("resolved_version")
    bundle_payload = metadata.get("policyengine_bundle")

    if not isinstance(resolved_app_name, str) or not resolved_app_name:
        raise ValueError("Missing resolved_app_name in batch metadata")
    if not isinstance(resolved_version, str) or not resolved_version:
        raise ValueError("Missing resolved_version in batch metadata")
    if not isinstance(bundle_payload, dict):
        raise ValueError("Missing policyengine_bundle in batch metadata")

    return (
        request,
        resolved_version,
        resolved_app_name,
        PolicyEngineBundle.model_validate(bundle_payload),
    )


def build_child_simulation_payload(
    params: dict[str, Any], *, year: str
) -> dict[str, Any]:
    payload = {
        key: value
        for key, value in params.items()
        if key
        not in {
            "version",
            "start_year",
            "window_size",
            "max_parallel",
            "_metadata",
            "_telemetry",
        }
    }
    payload["time_period"] = year

    telemetry = params.get("_telemetry")
    if isinstance(telemetry, dict):
        payload["_telemetry"] = telemetry

    return payload


def extract_budget_window_annual_impact(
    *, year: str, impact_data: dict[str, Any]
) -> BudgetWindowAnnualImpact:
    budget = impact_data.get("budget", {})
    state_tax_revenue_impact = budget.get("state_tax_revenue_impact", 0)
    tax_revenue_impact = budget.get("tax_revenue_impact", 0)

    return BudgetWindowAnnualImpact(
        year=year,
        taxRevenueImpact=tax_revenue_impact,
        federalTaxRevenueImpact=tax_revenue_impact - state_tax_revenue_impact,
        stateTaxRevenueImpact=state_tax_revenue_impact,
        benefitSpendingImpact=budget.get("benefit_spending_impact", 0),
        budgetaryImpact=budget.get("budgetary_impact", 0),
    )


def sum_budget_window_annual_impacts(
    annual_impacts: list[BudgetWindowAnnualImpact],
) -> BudgetWindowTotals:
    totals = {
        "taxRevenueImpact": 0,
        "federalTaxRevenueImpact": 0,
        "stateTaxRevenueImpact": 0,
        "benefitSpendingImpact": 0,
        "budgetaryImpact": 0,
    }

    for annual_impact in annual_impacts:
        totals["taxRevenueImpact"] += annual_impact.taxRevenueImpact
        totals["federalTaxRevenueImpact"] += annual_impact.federalTaxRevenueImpact
        totals["stateTaxRevenueImpact"] += annual_impact.stateTaxRevenueImpact
        totals["benefitSpendingImpact"] += annual_impact.benefitSpendingImpact
        totals["budgetaryImpact"] += annual_impact.budgetaryImpact

    return BudgetWindowTotals(**totals)


def build_budget_window_output(
    *,
    start_year: str,
    window_size: int,
    annual_impacts: list[BudgetWindowAnnualImpact],
) -> BudgetWindowResult:
    return BudgetWindowResult(
        startYear=start_year,
        endYear=str(int(start_year) + window_size - 1),
        windowSize=window_size,
        annualImpacts=annual_impacts,
        totals=sum_budget_window_annual_impacts(annual_impacts),
    )


def _failure_response(state) -> dict[str, Any]:
    return build_batch_status_response(state).model_dump(mode="json")


def run_budget_window_batch_impl(params: dict[str, Any]) -> dict[str, Any]:
    batch_job_id = modal.current_function_call_id()
    request, resolved_version, resolved_app_name, bundle = (
        _extract_request_and_metadata(params)
    )

    state = get_batch_job_seed(batch_job_id)
    if state is None:
        state = create_initial_batch_state(
            batch_job_id=batch_job_id,
            request=request,
            resolved_version=resolved_version,
            resolved_app_name=resolved_app_name,
            bundle=bundle,
        )
        put_batch_job_seed(state)

    mark_batch_running(state)
    put_batch_job_state(state)

    child_func = modal.Function.from_name(resolved_app_name, "run_simulation")
    child_calls: dict[str, Any] = {}

    while state.queued_years or state.running_years:
        while len(state.running_years) < state.max_parallel and state.queued_years:
            year = state.queued_years[0]
            child_payload = build_child_simulation_payload(params, year=year)
            call = child_func.spawn(child_payload)
            child_calls[year] = call
            mark_child_started(state, year=year, child_job_id=call.object_id)
            put_batch_job_state(state)

        progress_made = False
        for year in list(state.running_years):
            call = child_calls.get(year)
            if call is None:
                call = modal.FunctionCall.from_id(state.child_jobs[year].job_id)
                child_calls[year] = call

            try:
                result = call.get(timeout=0)
            except TimeoutError:
                continue
            except Exception as exc:
                error = str(exc)
                mark_child_failed(state, year=year, error=error)
                mark_batch_failed(state, error=error)
                put_batch_job_state(state)
                return _failure_response(state)

            annual_impact = extract_budget_window_annual_impact(
                year=year,
                impact_data=result,
            )
            mark_child_completed(state, year=year, annual_impact=annual_impact)
            put_batch_job_state(state)
            progress_made = True

        if state.running_years and not progress_made:
            time.sleep(POLL_INTERVAL_SECONDS)

    annual_impacts = [
        state.partial_annual_impacts[year]
        for year in state.years
        if year in state.partial_annual_impacts
    ]
    result = build_budget_window_output(
        start_year=state.start_year,
        window_size=state.window_size,
        annual_impacts=annual_impacts,
    )
    mark_batch_complete(state, result=result)
    put_batch_job_state(state)

    response = build_batch_status_response(state)
    return response.model_dump(mode="json")
