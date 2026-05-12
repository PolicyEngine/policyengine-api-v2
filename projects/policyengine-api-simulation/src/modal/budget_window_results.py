"""Budget-window result validation and aggregation helpers."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from src.modal.gateway.models import (
    BudgetWindowResult,
    BudgetWindowTotals,
    SingleYearMacroOutput,
)

# The UK microsimulation has no state/province fiscal layer, so worker child
# results for ``country="uk"`` never emit ``state_tax_revenue_impact``. The
# parent aggregator treats it as optional with a zero default; US results are
# expected to supply it as a real number. All other keys remain mandatory.
REQUIRED_BUDGET_KEYS = (
    "tax_revenue_impact",
    "benefit_spending_impact",
    "budgetary_impact",
)


def _is_number(value: Any) -> bool:
    return isinstance(value, int | float) and not isinstance(value, bool)


def _as_decimal(value: float | int) -> Decimal:
    """Convert an annual impact float to Decimal without reintroducing
    binary-float quantisation noise. ``Decimal(str(...))`` is the canonical
    idiom because it serialises the float to its shortest round-trippable
    decimal form before parsing."""

    return Decimal(str(value))


def validate_single_year_output(
    *,
    simulation_year: str,
    child_result: dict[str, Any],
) -> SingleYearMacroOutput:
    """Validate and normalize a child macro result.

    UK worker results can omit ``state_tax_revenue_impact`` because there is
    no state/province fiscal layer. The canonical output still includes that
    field, defaulted to zero, so downstream clients receive one stable shape.
    """

    if not isinstance(child_result, dict):
        raise ValueError(
            "Malformed budget-window child result: expected object for "
            f"{simulation_year}"
        )

    budget = child_result.get("budget", {})
    if not isinstance(budget, dict):
        raise ValueError("Malformed budget-window child result: missing budget object")

    missing_keys = [
        key
        for key in REQUIRED_BUDGET_KEYS
        if not _is_number(budget.get(key))
    ]
    if missing_keys:
        missing = ", ".join(f"budget.{key}" for key in missing_keys)
        raise ValueError(
            f"Malformed budget-window child result: missing numeric {missing}"
        )

    normalized = dict(child_result)
    normalized_budget = dict(budget)
    if "state_tax_revenue_impact" not in normalized_budget:
        normalized_budget["state_tax_revenue_impact"] = 0.0
    elif not _is_number(normalized_budget["state_tax_revenue_impact"]):
        raise ValueError(
            "Malformed budget-window child result: missing numeric "
            "budget.state_tax_revenue_impact"
        )
    normalized["budget"] = normalized_budget

    try:
        return SingleYearMacroOutput.model_validate(normalized)
    except Exception as exc:
        raise ValueError(
            f"Malformed budget-window child result for {simulation_year}: {exc}"
        ) from exc


def sum_single_year_outputs(
    *,
    outputs_by_year: dict[str, SingleYearMacroOutput],
    years: list[str],
) -> BudgetWindowTotals:
    """Sum per-year impacts using Decimal accumulators.

    Binary-float addition accumulates rounding error for long budget windows
    (10-year sums over billion-dollar baselines quickly drift by ``1e-6`` or
    more). Accumulating in :class:`decimal.Decimal` keeps the answer exact
    to the input precision; we cast back to ``float`` at the serialisation
    boundary so the JSON schema stays numeric and clients that parse the
    response as ``number`` continue to work unchanged. Clients that need
    bit-exact accounting should request the individual per-year impacts and
    sum them in their preferred numeric type.
    """

    totals: dict[str, Decimal] = {
        "taxRevenueImpact": Decimal(0),
        "federalTaxRevenueImpact": Decimal(0),
        "stateTaxRevenueImpact": Decimal(0),
        "benefitSpendingImpact": Decimal(0),
        "budgetaryImpact": Decimal(0),
    }

    for year in years:
        output = outputs_by_year[year]
        budget = output.model_dump(mode="json")["budget"]
        tax_revenue_impact = budget["tax_revenue_impact"]
        state_tax_revenue_impact = budget.get("state_tax_revenue_impact")

        totals["taxRevenueImpact"] += _as_decimal(tax_revenue_impact)
        totals["federalTaxRevenueImpact"] += _as_decimal(
            tax_revenue_impact - state_tax_revenue_impact
        )
        totals["stateTaxRevenueImpact"] += _as_decimal(state_tax_revenue_impact)
        totals["benefitSpendingImpact"] += _as_decimal(
            budget["benefit_spending_impact"]
        )
        totals["budgetaryImpact"] += _as_decimal(budget["budgetary_impact"])

    return BudgetWindowTotals(**{key: float(value) for key, value in totals.items()})


def build_budget_window_result(
    *,
    start_year: str,
    window_size: int,
    outputs_by_year: dict[str, SingleYearMacroOutput],
) -> BudgetWindowResult:
    years = [str(int(start_year) + offset) for offset in range(window_size)]
    missing_years = [year for year in years if year not in outputs_by_year]
    if missing_years:
        raise ValueError(
            "Cannot build budget-window result: missing outputs for "
            + ", ".join(missing_years)
        )

    ordered_outputs = {year: outputs_by_year[year] for year in years}
    return BudgetWindowResult(
        startYear=start_year,
        endYear=str(int(start_year) + window_size - 1),
        windowSize=window_size,
        years=years,
        outputsByYear=ordered_outputs,
        totals=sum_single_year_outputs(
            outputs_by_year=ordered_outputs,
            years=years,
        ),
    )
