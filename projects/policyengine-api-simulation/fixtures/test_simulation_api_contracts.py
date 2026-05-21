"""Fixtures for simulation API contract tests."""

CURRENT_SINGLE_YEAR_MACRO_KEYS = {
    "model_version",
    "data_version",
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

CURRENT_REQUIRED_BUDGET_KEYS = {
    "budgetary_impact",
    "tax_revenue_impact",
    "state_tax_revenue_impact",
    "benefit_spending_impact",
    "households",
    "baseline_net_income",
}

CURRENT_SINGLE_YEAR_MACRO_RESULT = {
    "model_version": "1.702.0",
    "data_version": "1.115.5",
    "budget": {
        "budgetary_impact": 300.0,
        "tax_revenue_impact": 500.0,
        "state_tax_revenue_impact": 125.0,
        "benefit_spending_impact": 200.0,
        "households": 2.0,
        "baseline_net_income": 1000.0,
    },
    "detailed_budget": {
        "income_tax": {
            "baseline": 1000.0,
            "reform": 1100.0,
            "difference": 100.0,
        }
    },
    "decile": {
        "relative": {"1": 0.01},
        "average": {"1": 10.0},
    },
    "inequality": {
        "baseline": {"gini": 0.3},
        "reform": {"gini": 0.29},
    },
    "poverty": {
        "poverty": {
            "adult": {"baseline": 0.1, "reform": 0.09},
            "all": {"baseline": 0.1, "reform": 0.09},
            "child": {"baseline": 0.12, "reform": 0.1},
            "senior": {"baseline": 0.08, "reform": 0.07},
        },
        "deep_poverty": {
            "adult": {"baseline": 0.03, "reform": 0.02},
            "all": {"baseline": 0.03, "reform": 0.02},
            "child": {"baseline": 0.04, "reform": 0.03},
            "senior": {"baseline": 0.02, "reform": 0.01},
        },
    },
    "poverty_by_gender": {
        "poverty": {
            "male": {"baseline": 0.1, "reform": 0.09},
            "female": {"baseline": 0.11, "reform": 0.1},
        },
        "deep_poverty": {
            "male": {"baseline": 0.03, "reform": 0.02},
            "female": {"baseline": 0.04, "reform": 0.03},
        },
    },
    "poverty_by_race": {
        "poverty": {
            "black": {"baseline": 0.12, "reform": 0.11},
            "hispanic": {"baseline": 0.13, "reform": 0.12},
            "other": {"baseline": 0.1, "reform": 0.09},
            "white": {"baseline": 0.08, "reform": 0.07},
        },
    },
    "intra_decile": {
        "all": {
            "Gain less than 5%": 0.2,
            "Gain more than 5%": 0.1,
            "Lose less than 5%": 0.1,
            "Lose more than 5%": 0.0,
            "No change": 0.6,
        },
        "deciles": {
            "Gain less than 5%": [0.2],
            "Gain more than 5%": [0.1],
            "Lose less than 5%": [0.1],
            "Lose more than 5%": [0.0],
            "No change": [0.6],
        },
    },
    "wealth_decile": None,
    "intra_wealth_decile": None,
    "labor_supply_response": {
        "substitution_lsr": 0.0,
        "income_lsr": 0.0,
        "relative_lsr": {},
        "total_change": 0.0,
        "revenue_change": 0.0,
        "decile": {},
        "hours": {"baseline": 0.0, "reform": 0.0, "change": 0.0},
    },
    "constituency_impact": None,
    "local_authority_impact": None,
    "congressional_district_impact": None,
    "cliff_impact": None,
}
