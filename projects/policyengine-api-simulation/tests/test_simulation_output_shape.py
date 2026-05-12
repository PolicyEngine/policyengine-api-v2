"""Regression coverage for worker macro output shaping."""

from types import SimpleNamespace

import src.modal.simulation as simulation_module
from tests.fixtures.budget_window_outputs import FULL_SINGLE_YEAR_MACRO_OUTPUT_KEYS


class FakeDataFrame:
    def __init__(self, rows: list[dict]):
        self.rows = rows

    def to_dict(self, orient: str):
        assert orient == "records"
        return self.rows


def _collection(rows: list[dict]):
    return SimpleNamespace(dataframe=FakeDataFrame(rows))


def _metric_pair(baseline: float = 0.0, reform: float = 0.0) -> dict[str, float]:
    return {"baseline": baseline, "reform": reform}


def test_legacy_macro_result_restores_full_single_year_shape(monkeypatch):
    decile_rows = [
        {"decile": 2, "absolute_change": 200.0, "relative_change": 0.02},
        {"decile": 1, "absolute_change": 100.0, "relative_change": 0.01},
    ]
    program_rows = [
        {
            "program_name": "income_tax",
            "baseline_total": 1000.0,
            "reform_total": 1100.0,
            "change": 100.0,
        }
    ]
    intra_decile_rows = [
        {
            "decile": 0,
            "gain_less_than_5pct": 0.1,
            "gain_more_than_5pct": 0.2,
            "lose_less_than_5pct": 0.3,
            "lose_more_than_5pct": 0.4,
            "no_change": 0.0,
        },
        {
            "decile": 1,
            "gain_less_than_5pct": 0.5,
            "gain_more_than_5pct": 0.6,
            "lose_less_than_5pct": 0.7,
            "lose_more_than_5pct": 0.8,
            "no_change": 0.9,
        },
    ]
    poverty = {
        "poverty": {"all": _metric_pair(0.1, 0.2)},
        "deep_poverty": {"all": _metric_pair(0.03, 0.04)},
    }
    poverty_by_gender = {
        "poverty": {"male": _metric_pair(0.1, 0.2)},
        "deep_poverty": {"male": _metric_pair(0.03, 0.04)},
    }
    poverty_by_race = {"poverty": {"white": _metric_pair(0.1, 0.2)}}

    analysis = SimpleNamespace(
        decile_impacts=_collection(decile_rows),
        program_statistics=_collection(program_rows),
        baseline_inequality=SimpleNamespace(
            gini=0.31,
            top_10_share=0.42,
            top_1_share=0.12,
        ),
        reform_inequality=SimpleNamespace(
            gini=0.32,
            top_10_share=0.43,
            top_1_share=0.13,
        ),
    )

    monkeypatch.setattr(
        simulation_module,
        "_try_intra_decile_rows",
        lambda country, baseline, reform: intra_decile_rows,
    )
    monkeypatch.setattr(
        simulation_module,
        "_poverty_result",
        lambda country, baseline, reform: poverty,
    )
    monkeypatch.setattr(
        simulation_module,
        "_poverty_by_gender_result",
        lambda country, baseline, reform: poverty_by_gender,
    )
    monkeypatch.setattr(
        simulation_module,
        "_poverty_by_race_result",
        lambda country, baseline, reform: poverty_by_race,
    )
    monkeypatch.setattr(
        simulation_module,
        "_congressional_district_impact",
        lambda country, baseline, reform: {"districts": []},
    )
    monkeypatch.setattr(
        simulation_module,
        "_package_version",
        lambda package: {"policyengine-us": "1.500.0", "policyengine": "4.4.3"}.get(
            package
        ),
    )

    result = simulation_module._legacy_macro_result(
        country="us",
        params={"data_version": "data-v1"},
        baseline=object(),
        reform=object(),
        analysis=analysis,
        budget={
            "tax_revenue_impact": 100.0,
            "state_tax_revenue_impact": 20.0,
            "benefit_spending_impact": 30.0,
            "budgetary_impact": 70.0,
            "baseline_net_income": 1000.0,
            "households": 10.0,
        },
        metadata={"country": "us", "year": 2026, "dataset": "dataset.h5"},
    )

    assert FULL_SINGLE_YEAR_MACRO_OUTPUT_KEYS <= result.keys()
    assert result["budget"]["baseline_net_income"] == 1000.0
    assert result["budget"]["households"] == 10.0
    assert result["detailed_budget"]["income_tax"] == {
        "baseline": 1000.0,
        "reform": 1100.0,
        "difference": 100.0,
    }
    assert result["decile"] == {
        "average": {"1": 100.0, "2": 200.0},
        "relative": {"1": 0.01, "2": 0.02},
    }
    assert result["inequality"]["gini"] == {"baseline": 0.31, "reform": 0.32}
    assert result["poverty"] is poverty
    assert result["poverty_by_gender"] is poverty_by_gender
    assert result["poverty_by_race"] is poverty_by_race
    assert result["intra_decile"]["all"]["Gain more than 5%"] == 0.2
    assert result["intra_decile"]["deciles"]["Gain more than 5%"] == [0.6]
    assert result["labor_supply_response"]["hours"]["baseline"] == 0.0
    assert result["model_version"] == "1.500.0"
    assert result["policyengine_version"] == "4.4.3"
    assert result["data_version"] == "data-v1"
    assert result["dataset"] == "dataset.h5"
    assert result["decile_impacts"] == decile_rows
    assert result["program_statistics"] == program_rows
    assert result["intra_decile_rows"] == intra_decile_rows


def test_budget_result_keeps_state_tax_field_for_all_countries(monkeypatch):
    def fake_change_sum(baseline, reform, variable: str, entity=None):
        return {
            "household_tax": 100.0,
            "household_benefits": 30.0,
            "household_state_income_tax": 12.0,
        }[variable]

    monkeypatch.setattr(simulation_module, "_try_change_sum", fake_change_sum)
    monkeypatch.setattr(
        simulation_module,
        "_try_aggregate_sum",
        lambda simulation, variable, entity=None: 1000.0,
    )
    monkeypatch.setattr(
        simulation_module,
        "_try_aggregate_count",
        lambda simulation, variable, entity=None: 10.0,
    )

    uk_budget = simulation_module._budget_result("uk", object(), object())
    us_budget = simulation_module._budget_result("us", object(), object())

    assert uk_budget == {
        "tax_revenue_impact": 100.0,
        "state_tax_revenue_impact": 0.0,
        "benefit_spending_impact": 30.0,
        "budgetary_impact": 70.0,
        "baseline_net_income": 1000.0,
        "households": 10.0,
    }
    assert us_budget["state_tax_revenue_impact"] == 12.0


def test_congressional_district_rows_use_legacy_report_shape():
    rows = simulation_module._congressional_district_rows(
        [
            {
                "state_fips": 6,
                "district_number": 12,
                "average_household_income_change": 100.0,
                "relative_household_income_change": 0.01,
                "winner_percentage": 0.4,
                "loser_percentage": 0.1,
                "no_change_percentage": 0.5,
                "district_geoid": 612,
            }
        ]
    )

    assert rows == [
        {
            "district": "06-12",
            "average_household_income_change": 100.0,
            "relative_household_income_change": 0.01,
            "winner_percentage": 0.4,
            "loser_percentage": 0.1,
            "no_change_percentage": 0.5,
        }
    ]
