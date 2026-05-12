"""Tests for gateway response serialization helpers."""

import json

from src.modal.gateway.models import (
    BatchChildJobStatus,
    BudgetWindowBatchStatusResponse,
    BudgetWindowResult,
    BudgetWindowTotals,
)
from src.modal.gateway.responses import batch_status_response, complete_job_response
from tests.fixtures.budget_window_outputs import make_single_year_macro_output


def test_complete_budget_window_response_preserves_null_annual_sections():
    response = BudgetWindowBatchStatusResponse(
        status="complete",
        progress=100,
        completed_years=["2026"],
        running_years=[],
        queued_years=[],
        failed_years=[],
        child_jobs={"2026": BatchChildJobStatus(job_id="fc-2026", status="complete")},
        result=BudgetWindowResult(
            startYear="2026",
            endYear="2026",
            windowSize=1,
            years=["2026"],
            outputsByYear={
                "2026": make_single_year_macro_output(
                    tax_revenue_impact=10,
                    state_tax_revenue_impact=0,
                    benefit_spending_impact=5,
                    budgetary_impact=5,
                )
            },
            totals=BudgetWindowTotals(
                taxRevenueImpact=10,
                federalTaxRevenueImpact=10,
                stateTaxRevenueImpact=0,
                benefitSpendingImpact=5,
                budgetaryImpact=5,
            ),
        ),
    )

    serialized = batch_status_response(response)
    body = json.loads(serialized.body)
    output = body["result"]["outputsByYear"]["2026"]

    assert "wealth_decile" in output
    assert output["wealth_decile"] is None
    assert "congressional_district_impact" in output
    assert output["congressional_district_impact"] is None


def test_complete_job_response_preserves_null_result_sections():
    result = make_single_year_macro_output(
        tax_revenue_impact=10,
        state_tax_revenue_impact=0,
        benefit_spending_impact=5,
        budgetary_impact=5,
    )

    serialized = complete_job_response(result=result)
    body = json.loads(serialized.body)
    output = body["result"]

    assert "wealth_decile" in output
    assert output["wealth_decile"] is None
    assert "congressional_district_impact" in output
    assert output["congressional_district_impact"] is None
