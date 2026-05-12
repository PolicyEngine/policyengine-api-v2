"""Budget-window output fixtures used by scheduler/result tests."""

from __future__ import annotations

from copy import deepcopy


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


def _baseline_reform_values() -> dict[str, float]:
    return {"baseline": 0.0, "reform": 0.0}


def _age_group_values() -> dict[str, dict[str, float]]:
    values = _baseline_reform_values()
    return {
        "child": deepcopy(values),
        "adult": deepcopy(values),
        "senior": deepcopy(values),
        "all": deepcopy(values),
    }


def _gender_values() -> dict[str, dict[str, float]]:
    values = _baseline_reform_values()
    return {
        "male": deepcopy(values),
        "female": deepcopy(values),
    }


def make_single_year_macro_output(
    *,
    tax_revenue_impact: float,
    state_tax_revenue_impact: float | None = 0.0,
    benefit_spending_impact: float,
    budgetary_impact: float,
) -> dict:
    """Return a minimal valid single-year macro output payload."""

    budget = {
        "budgetary_impact": budgetary_impact,
        "tax_revenue_impact": tax_revenue_impact,
        "benefit_spending_impact": benefit_spending_impact,
        "households": 1.0,
        "baseline_net_income": 1000.0,
    }
    if state_tax_revenue_impact is not None:
        budget["state_tax_revenue_impact"] = state_tax_revenue_impact

    return {
        "budget": budget,
        "detailed_budget": {
            "income_tax": {"baseline": 100.0, "reform": 110.0, "difference": 10.0}
        },
        "decile": {"relative": {"1": 0.01}, "average": {"1": 100.0}},
        "inequality": {
            "gini": _baseline_reform_values(),
            "top_10_pct_share": _baseline_reform_values(),
            "top_1_pct_share": _baseline_reform_values(),
        },
        "poverty": {
            "poverty": _age_group_values(),
            "deep_poverty": _age_group_values(),
        },
        "poverty_by_gender": {
            "poverty": _gender_values(),
            "deep_poverty": _gender_values(),
        },
        "poverty_by_race": None,
        "intra_decile": {"deciles": {}, "all": {}},
        "wealth_decile": None,
        "intra_wealth_decile": None,
        "labor_supply_response": {
            "substitution_lsr": 0.0,
            "income_lsr": 0.0,
            "relative_lsr": {},
            "total_change": 0.0,
            "revenue_change": 0.0,
            "decile": {},
            "hours": {
                "baseline": 0.0,
                "reform": 0.0,
                "change": 0.0,
                "income_effect": 0.0,
                "substitution_effect": 0.0,
            },
        },
        "constituency_impact": None,
        "local_authority_impact": None,
        "congressional_district_impact": None,
        "cliff_impact": None,
        "model_version": "1.500.0",
        "policyengine_version": "4.4.3",
        "data_version": None,
        "dataset": "fixture-dataset.h5",
        "metadata": {"country": "us", "year": 2026, "dataset": "fixture-dataset.h5"},
        "decile_impacts": [
            {"decile": 1, "absolute_change": 100.0, "relative_change": 0.01}
        ],
        "program_statistics": [
            {
                "program_name": "income_tax",
                "baseline_total": 100.0,
                "reform_total": 110.0,
                "change": 10.0,
            }
        ],
        "intra_decile_rows": [],
    }
