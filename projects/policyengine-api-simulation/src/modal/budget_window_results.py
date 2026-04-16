"""Budget-window annual result extraction and aggregation helpers."""

from __future__ import annotations

from typing import Any

from src.modal.gateway.models import (
    BudgetWindowAnnualImpact,
    BudgetWindowResult,
    BudgetWindowTotals,
)

REQUIRED_BUDGET_KEYS = (
    "tax_revenue_impact",
    "state_tax_revenue_impact",
    "benefit_spending_impact",
    "budgetary_impact",
)


def extract_annual_impact(
    *,
    simulation_year: str,
    child_result: dict[str, Any],
) -> BudgetWindowAnnualImpact:
    budget = child_result.get("budget", {})
    if not isinstance(budget, dict):
        raise ValueError("Malformed budget-window child result: missing budget object")

    missing_keys = [
        key
        for key in REQUIRED_BUDGET_KEYS
        if not isinstance(budget.get(key), int | float)
    ]
    if missing_keys:
        missing = ", ".join(f"budget.{key}" for key in missing_keys)
        raise ValueError(
            f"Malformed budget-window child result: missing numeric {missing}"
        )

    state_tax_revenue_impact = budget["state_tax_revenue_impact"]
    tax_revenue_impact = budget["tax_revenue_impact"]

    return BudgetWindowAnnualImpact(
        year=simulation_year,
        taxRevenueImpact=tax_revenue_impact,
        federalTaxRevenueImpact=tax_revenue_impact - state_tax_revenue_impact,
        stateTaxRevenueImpact=state_tax_revenue_impact,
        benefitSpendingImpact=budget["benefit_spending_impact"],
        budgetaryImpact=budget["budgetary_impact"],
    )


def sum_annual_impacts(
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


def build_budget_window_result(
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
        totals=sum_annual_impacts(annual_impacts),
    )
