"""Tests for translating PolicyEngine v4 outputs into API-v2 macro results."""

from __future__ import annotations

from types import SimpleNamespace

import pandas as pd

from fixtures.test_simulation_api_contracts import CURRENT_SINGLE_YEAR_MACRO_KEYS
from fixtures.test_simulation_output_adapter import (
    BASELINE_POVERTY_BY_AGE,
    BASELINE_POVERTY_BY_GENDER,
    BASELINE_POVERTY_BY_RACE,
    BUDGET,
    INTRA_DECILE_COLLECTION,
    REFORM_POVERTY_BY_AGE,
    REFORM_POVERTY_BY_GENDER,
    REFORM_POVERTY_BY_RACE,
    fake_analysis,
)
from src.modal.simulation import _budget_result, _normalise_policy
from src.modal.simulation_output_adapter import adapt_analysis_to_legacy_macro_output


def test_adapter_returns_existing_single_year_macro_shape():
    output = adapt_analysis_to_legacy_macro_output(
        country="us",
        model_version="1.691.12",
        data_version="1.115.3",
        budget=BUDGET,
        analysis=fake_analysis(),
        baseline_poverty_by_age=BASELINE_POVERTY_BY_AGE,
        reform_poverty_by_age=REFORM_POVERTY_BY_AGE,
        baseline_poverty_by_gender=BASELINE_POVERTY_BY_GENDER,
        reform_poverty_by_gender=REFORM_POVERTY_BY_GENDER,
        baseline_poverty_by_race=BASELINE_POVERTY_BY_RACE,
        reform_poverty_by_race=REFORM_POVERTY_BY_RACE,
        intra_decile=INTRA_DECILE_COLLECTION,
        congressional_district_impact=[{"district_geoid": 101}],
    )

    assert set(output) == CURRENT_SINGLE_YEAR_MACRO_KEYS
    assert output["model_version"] == "1.691.12"
    assert output["data_version"] == "1.115.3"
    assert output["budget"] == BUDGET
    assert output["detailed_budget"] == {
        "income_tax": {"baseline": 100.0, "reform": 125.0, "difference": 25.0}
    }
    assert output["decile"] == {
        "average": {"1": 10.0, "2": 20.0},
        "relative": {"1": 0.01, "2": 0.02},
    }
    assert output["intra_decile"]["deciles"]["Gain more than 5%"] == [0.5, 0.1]
    assert output["intra_decile"]["all"]["Gain more than 5%"] == 0.3
    assert output["poverty"]["poverty"]["all"] == {
        "baseline": 0.10,
        "reform": 0.09,
    }
    assert output["poverty"]["poverty"]["child"] == {
        "baseline": 0.12,
        "reform": 0.11,
    }
    assert output["poverty_by_gender"]["poverty"]["male"] == {
        "baseline": 0.08,
        "reform": 0.07,
    }
    assert output["poverty_by_race"]["poverty"]["white"] == {
        "baseline": 0.06,
        "reform": 0.05,
    }
    assert output["wealth_decile"] is None
    assert output["intra_wealth_decile"] is None
    assert output["congressional_district_impact"] == [{"district_geoid": 101}]


def test_adapter_maps_uk_wealth_outputs_and_omits_us_only_race():
    output = adapt_analysis_to_legacy_macro_output(
        country="uk",
        model_version="2.88.14",
        data_version="1.55.5",
        budget={**BUDGET, "state_tax_revenue_impact": 0.0},
        analysis=fake_analysis(),
        intra_decile=INTRA_DECILE_COLLECTION,
    )

    assert output["poverty_by_race"] is None
    assert output["wealth_decile"] == {
        "average": {"1": 30.0},
        "relative": {"1": 0.03},
    }
    assert output["intra_wealth_decile"]["deciles"]["Lose more than 5%"] == [0.1]


def test_normalise_policy_converts_legacy_period_range_keys():
    assert _normalise_policy({"gov.test.parameter": {"2026-01-01.2100-12-31": 1}}) == {
        "gov.test.parameter": {"2026-01-01": 1}
    }


class _FakeOutputDataset:
    def __init__(self, household):
        self.data = SimpleNamespace(household=household)


class _FakeSimulation:
    def __init__(self, household):
        self.output_dataset = _FakeOutputDataset(household)

    def ensure(self):
        raise AssertionError("test data is already materialized")


def test_budget_result_uses_materialized_household_columns_and_uk_state_tax_zero():
    baseline = _FakeSimulation(
        pd.DataFrame(
            {
                "household_weight": [1.0, 2.0],
                "household_net_income": [100.0, 200.0],
                "household_tax": [20.0, 40.0],
                "household_benefits": [5.0, 10.0],
                "household_state_income_tax": [2.0, 3.0],
            }
        )
    )
    reform = _FakeSimulation(
        pd.DataFrame(
            {
                "household_weight": [1.0, 2.0],
                "household_net_income": [120.0, 210.0],
                "household_tax": [25.0, 50.0],
                "household_benefits": [4.0, 8.0],
                "household_state_income_tax": [4.0, 6.0],
            }
        )
    )

    us_budget = _budget_result("us", baseline, reform)
    uk_budget = _budget_result("uk", baseline, reform)

    assert us_budget == {
        "tax_revenue_impact": 15.0,
        "state_tax_revenue_impact": 5.0,
        "benefit_spending_impact": -3.0,
        "budgetary_impact": 18.0,
        "households": 3.0,
        "baseline_net_income": 300.0,
    }
    assert uk_budget["state_tax_revenue_impact"] == 0.0
