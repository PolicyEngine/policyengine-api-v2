"""
Integration tests for Modal-based budget-window batches.

These tests run against the staging Modal deployment and verify that the
gateway can spawn the parent budget-window worker, the parent can spawn child
simulation workers, and the completed batch result has the public response
shape expected by API consumers.
"""

from collections.abc import Mapping
from http import HTTPStatus

import pytest

from policyengine_api_simulation_client.models import (
    BudgetWindowBatchSubmitResponse,
    BudgetWindowResult,
)
from policyengine_api_simulation_client.types import Unset


FULL_SINGLE_YEAR_MACRO_OUTPUT_KEYS = {
    "budget",
    "detailed_budget",
    "decile",
    "inequality",
    "poverty",
    "poverty_by_gender",
    "poverty_by_race",
    "intra_decile",
    "wealth_decile",
    "intra_wealth_decile",
    "labor_supply_response",
    "constituency_impact",
    "local_authority_impact",
    "congressional_district_impact",
    "cliff_impact",
}
BUDGET_OUTPUT_KEYS = {
    "baseline_net_income",
    "benefit_spending_impact",
    "budgetary_impact",
    "households",
    "state_tax_revenue_impact",
    "tax_revenue_impact",
}


def assert_full_single_year_macro_output(output: object) -> None:
    payload = output.to_dict()
    missing = FULL_SINGLE_YEAR_MACRO_OUTPUT_KEYS - payload.keys()
    assert not missing, f"Missing full macro fields: {sorted(missing)}"
    assert "annualImpacts" not in payload

    budget = payload["budget"]
    assert isinstance(budget, Mapping)
    missing_budget_keys = BUDGET_OUTPUT_KEYS - budget.keys()
    assert not missing_budget_keys, (
        f"Missing budget fields: {sorted(missing_budget_keys)}"
    )
    assert isinstance(payload["detailed_budget"], Mapping)
    assert isinstance(payload["decile"], Mapping)
    assert isinstance(payload["poverty"], Mapping)
    assert isinstance(payload["poverty_by_gender"], Mapping)
    assert isinstance(payload["intra_decile"], Mapping)
    assert isinstance(payload["labor_supply_response"], Mapping)
    assert "decile_impacts" in payload
    assert "program_statistics" in payload


@pytest.mark.beta_only
def test_budget_window_multi_year_batch_completes(
    budget_window_request,
    budget_window_years,
    decode_response_content,
    submit_budget_window_batch,
    poll_budget_window_batch,
    us_model_version: str,
):
    """
    Given a two-year US budget-window request
    When the batch is submitted and polled to completion
    Then the response contains 2026 and 2027 full outputs plus totals.
    """
    submit_response = submit_budget_window_batch(budget_window_request)

    assert submit_response.status_code == HTTPStatus.OK, (
        "Unexpected submit status "
        f"{submit_response.status_code}: "
        f"{decode_response_content(submit_response.content)}"
    )
    assert isinstance(submit_response.parsed, BudgetWindowBatchSubmitResponse), (
        f"Unexpected response type: {type(submit_response.parsed)}"
    )
    assert submit_response.parsed.status == "submitted"
    assert submit_response.parsed.version == us_model_version

    batch_job_id = submit_response.parsed.batch_job_id
    assert submit_response.parsed.poll_url == f"/budget-window-jobs/{batch_job_id}"

    completed = poll_budget_window_batch(batch_job_id)

    assert completed.status == "complete"
    assert completed.progress == 100
    assert completed.error is None or isinstance(completed.error, Unset)
    assert isinstance(completed.result, BudgetWindowResult)

    result = completed.result
    assert result.kind == "budgetWindow"
    assert result.start_year == budget_window_years[0]
    assert result.end_year == budget_window_years[-1]
    assert result.window_size == len(budget_window_years)
    assert result.years == budget_window_years
    outputs_by_year = result.outputs_by_year
    assert not isinstance(outputs_by_year, Unset)
    assert outputs_by_year.additional_keys == budget_window_years
    assert all(
        outputs_by_year[year].budget.budgetary_impact is not None
        for year in budget_window_years
    )
    for year in budget_window_years:
        assert_full_single_year_macro_output(outputs_by_year[year])
    assert isinstance(result.totals.budgetary_impact, int | float)
