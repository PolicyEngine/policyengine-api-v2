"""
Integration tests for Modal-based budget-window batches.

These tests run against the staging Modal deployment and verify that the
gateway can spawn the parent budget-window worker, the parent can spawn child
simulation workers, and the completed batch result has the public response
shape expected by API consumers.
"""

from http import HTTPStatus

import pytest

from policyengine_api_simulation_client.models import (
    BudgetWindowBatchSubmitResponse,
    BudgetWindowResult,
    SingleYearMacroOutput,
)
from policyengine_api_simulation_client.types import Unset

SINGLE_YEAR_MACRO_OUTPUT_KEYS = {
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
    result_payload = result.to_dict()
    assert "annualImpacts" not in result_payload
    assert "outputsByYear" in result_payload

    outputs_by_year = result.outputs_by_year
    assert not isinstance(outputs_by_year, Unset)
    assert outputs_by_year.additional_keys == budget_window_years
    for year in budget_window_years:
        output = outputs_by_year[year]
        assert isinstance(output, SingleYearMacroOutput)
        output_payload = output.to_dict()
        assert SINGLE_YEAR_MACRO_OUTPUT_KEYS <= set(output_payload)
        assert output.budget.budgetary_impact is not None
        assert isinstance(output_payload["decile"], dict)
        assert isinstance(output_payload["inequality"], dict)
        assert isinstance(output_payload["poverty"], dict)
        assert isinstance(output_payload["poverty_by_gender"], dict)
        assert isinstance(output_payload["intra_decile"], dict)
        assert isinstance(output_payload["labor_supply_response"], dict)

    assert isinstance(result.totals.budgetary_impact, int | float)
