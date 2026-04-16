"""Tests for budget-window batch result helpers."""

import pytest

from src.modal.budget_window_results import (
    build_budget_window_result,
    extract_annual_impact,
    sum_annual_impacts,
)
from src.modal.gateway.models import BudgetWindowAnnualImpact


def test_extract_annual_impact_matches_v1_shape():
    annual = extract_annual_impact(
        simulation_year="2026",
        child_result={
            "budget": {
                "tax_revenue_impact": 100,
                "state_tax_revenue_impact": 40,
                "benefit_spending_impact": 20,
                "budgetary_impact": 80,
            }
        },
    )

    assert annual == BudgetWindowAnnualImpact(
        year="2026",
        taxRevenueImpact=100,
        federalTaxRevenueImpact=60,
        stateTaxRevenueImpact=40,
        benefitSpendingImpact=20,
        budgetaryImpact=80,
    )


def test_extract_annual_impact_rejects_malformed_child_result():
    with pytest.raises(
        ValueError,
        match="Malformed budget-window child result: missing numeric budget.tax_revenue_impact",
    ):
        extract_annual_impact(
            simulation_year="2026",
            child_result={
                "budget": {
                    "state_tax_revenue_impact": 40,
                    "benefit_spending_impact": 20,
                    "budgetary_impact": 80,
                }
            },
        )


def test_build_budget_window_result_sums_totals():
    annual_impacts = [
        BudgetWindowAnnualImpact(
            year="2026",
            taxRevenueImpact=10,
            federalTaxRevenueImpact=7,
            stateTaxRevenueImpact=3,
            benefitSpendingImpact=5,
            budgetaryImpact=15,
        ),
        BudgetWindowAnnualImpact(
            year="2027",
            taxRevenueImpact=11,
            federalTaxRevenueImpact=8,
            stateTaxRevenueImpact=3,
            benefitSpendingImpact=6,
            budgetaryImpact=17,
        ),
    ]

    totals = sum_annual_impacts(annual_impacts)
    result = build_budget_window_result(
        start_year="2026",
        window_size=2,
        annual_impacts=annual_impacts,
    )

    assert totals.budgetaryImpact == 32
    assert result.endYear == "2027"
    assert result.totals.taxRevenueImpact == 21
    assert result.totals.budgetaryImpact == 32
