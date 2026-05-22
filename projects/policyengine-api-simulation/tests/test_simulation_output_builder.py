"""Tests for building PolicyEngine v4 outputs into API-v2 macro results."""

from __future__ import annotations

from types import SimpleNamespace

import pandas as pd
import pytest

from fixtures.test_simulation_api_contracts import (
    CURRENT_SINGLE_YEAR_MACRO_KEYS,
    CURRENT_SINGLE_YEAR_MACRO_RESULT,
)
from fixtures.test_simulation_output_builder import (
    BASELINE_POVERTY_BY_AGE,
    BASELINE_POVERTY_BY_GENDER,
    BASELINE_POVERTY_BY_RACE,
    INTRA_DECILE_COLLECTION,
    REFORM_POVERTY_BY_AGE,
    REFORM_POVERTY_BY_GENDER,
    REFORM_POVERTY_BY_RACE,
    fake_analysis,
)
from src.modal.simulation import _normalise_policy
from src.modal.simulation import _run_simulation_impl_core
from src.modal.simulation_macro_output import (
    BudgetaryImpact,
    BudgetaryOutput,
    DecileOutput,
    DetailedBudgetOutput,
    GeographicImpactOutput,
    IntraDecileOutput,
    PovertyOutput,
    SingleYearMacroOutput,
)
from src.modal.simulation_output_builder import SimulationOutputBuilder


class _FakeOutputDataset:
    def __init__(self, household):
        self.data = SimpleNamespace(household=household)


class _FakeSimulation:
    def __init__(self, household):
        self.output_dataset = _FakeOutputDataset(household)

    def ensure(self):
        raise AssertionError("test data is already materialized")


def _macro_baseline_reform():
    baseline = _FakeSimulation(
        pd.DataFrame(
            {
                "household_weight": [1.0, 1.0],
                "household_net_income": [400.0, 600.0],
                "household_tax": [50.0, 50.0],
                "household_benefits": [20.0, 30.0],
                "household_state_income_tax": [5.0, 5.0],
            }
        )
    )
    reform = _FakeSimulation(
        pd.DataFrame(
            {
                "household_weight": [1.0, 1.0],
                "household_net_income": [410.0, 620.0],
                "household_tax": [100.0, 100.0],
                "household_benefits": [35.0, 45.0],
                "household_state_income_tax": [15.0, 15.0],
            }
        )
    )
    return baseline, reform


def _simulation_output_builder(
    country: str,
    baseline,
    reform,
    analysis=None,
) -> SimulationOutputBuilder:
    analysis = analysis or fake_analysis()
    country_module = SimpleNamespace(
        model=SimpleNamespace(version="1.700.0" if country == "us" else "2.88.20"),
        economic_impact_analysis=lambda baseline_simulation, reform_simulation: (
            analysis
        ),
    )
    return SimulationOutputBuilder(
        country=country,
        simulation_params={
            "country": country,
            "data_version": "1.115.5" if country == "us" else "1.55.10",
        },
        country_module=country_module,
        dataset=SimpleNamespace(metadata={}),
        baseline=baseline,
        reform=reform,
    )


def _stub_policyengine_output_calls(monkeypatch, baseline, reform) -> None:
    def fake_poverty_module_function(name):
        def compute(simulation):
            if "by_age" in name:
                return (
                    BASELINE_POVERTY_BY_AGE
                    if simulation is baseline
                    else REFORM_POVERTY_BY_AGE
                )
            if "by_gender" in name:
                return (
                    BASELINE_POVERTY_BY_GENDER
                    if simulation is baseline
                    else REFORM_POVERTY_BY_GENDER
                )
            if "by_race" in name:
                return (
                    BASELINE_POVERTY_BY_RACE
                    if simulation is baseline
                    else REFORM_POVERTY_BY_RACE
                )
            raise AssertionError(f"Unexpected poverty output: {name}")

        return compute

    monkeypatch.setattr(
        "src.modal.simulation_output_builder._poverty_module_function",
        fake_poverty_module_function,
    )
    monkeypatch.setattr(
        SimulationOutputBuilder,
        "_build_intra_decile_output",
        lambda self: self._build_intra_decile_output_from_collection(
            INTRA_DECILE_COLLECTION
        ),
    )
    monkeypatch.setattr(
        SimulationOutputBuilder,
        "_build_congressional_district_impact",
        lambda self: (
            self._build_geographic_impact_output([{"district_geoid": 101}])
            if self.country == "us"
            else None
        ),
    )
    monkeypatch.setattr(
        SimulationOutputBuilder,
        "_build_uk_constituency_impact",
        lambda self: (
            self._build_geographic_impact_output([{"constituency_code": "E14000530"}])
            if self.country == "uk"
            else None
        ),
    )
    monkeypatch.setattr(
        SimulationOutputBuilder,
        "_build_uk_local_authority_impact",
        lambda self: (
            self._build_geographic_impact_output(
                [{"local_authority_code": "E06000001"}]
            )
            if self.country == "uk"
            else None
        ),
    )


def _build_schema_output(monkeypatch, *, country: str = "us") -> SingleYearMacroOutput:
    baseline, reform = _macro_baseline_reform()
    _stub_policyengine_output_calls(monkeypatch, baseline, reform)
    return _simulation_output_builder(country, baseline, reform).build()


def test_builder_returns_schema_modules_before_legacy_dict_dump(monkeypatch):
    output = _build_schema_output(monkeypatch)

    assert isinstance(output, SingleYearMacroOutput)
    assert isinstance(output.budget, BudgetaryOutput)
    assert isinstance(output.budget, BudgetaryImpact)
    assert isinstance(output.detailed_budget, DetailedBudgetOutput)
    assert isinstance(output.decile, DecileOutput)
    assert isinstance(output.intra_decile, IntraDecileOutput)
    assert isinstance(output.poverty, PovertyOutput)
    assert isinstance(output.congressional_district_impact, GeographicImpactOutput)
    assert output.wealth_decile is None
    assert output.congressional_district_impact.root == [{"district_geoid": 101}]


def test_builder_returns_existing_single_year_macro_shape(monkeypatch):
    output = _build_schema_output(monkeypatch).model_dump(mode="json")

    assert set(output) == CURRENT_SINGLE_YEAR_MACRO_KEYS
    assert output == CURRENT_SINGLE_YEAR_MACRO_RESULT


def test_builder_maps_uk_wealth_outputs_and_omits_us_only_race(monkeypatch):
    output = _build_schema_output(monkeypatch, country="uk").model_dump(mode="json")

    assert output["poverty_by_race"] is None
    assert output["wealth_decile"] == {
        "average": {"1": 30.0},
        "relative": {"1": 0.03},
    }
    assert output["intra_wealth_decile"]["deciles"]["Lose more than 5%"] == [0.1]
    assert output["constituency_impact"] == [{"constituency_code": "E14000530"}]
    assert output["local_authority_impact"] == [{"local_authority_code": "E06000001"}]


def test_builder_calls_policyengine_economic_impact_analysis():
    baseline, reform = _macro_baseline_reform()
    analysis = fake_analysis()
    calls = []
    country_module = SimpleNamespace(
        model=SimpleNamespace(version="1.700.0"),
        economic_impact_analysis=lambda baseline_simulation, reform_simulation: (
            calls.append((baseline_simulation, reform_simulation)) or analysis
        ),
    )
    builder = SimulationOutputBuilder(
        country="us",
        simulation_params={"country": "us", "data_version": "1.115.5"},
        country_module=country_module,
        dataset=SimpleNamespace(metadata={}),
        baseline=baseline,
        reform=reform,
    )

    assert builder.analysis is analysis
    assert builder.analysis is analysis
    assert calls == [(baseline, reform)]


def test_normalise_policy_converts_legacy_period_range_keys():
    assert _normalise_policy({"gov.test.parameter": {"2026-01-01.2100-12-31": 1}}) == {
        "gov.test.parameter": {"2026-01-01": 1}
    }


def test_run_simulation_impl_core_builds_and_serializes_macro_output(monkeypatch):
    dataset = object()
    country_module = SimpleNamespace(model=SimpleNamespace(version="1.700.0"))
    baseline_simulation = object()
    reform_simulation = object()
    build_calls = []
    builder_calls = []

    def fake_country_module(country):
        assert country == "us"
        return country_module

    def fake_build_simulation(params, *, dataset, policy):
        build_calls.append((params, dataset, policy))
        return baseline_simulation if len(build_calls) == 1 else reform_simulation

    class FakeSimulationOutputBuilder:
        def __init__(self, **kwargs):
            builder_calls.append(kwargs)

        def serialize(self):
            return CURRENT_SINGLE_YEAR_MACRO_RESULT

    monkeypatch.setattr("src.modal.simulation._country_module", fake_country_module)
    monkeypatch.setattr("src.modal.simulation._load_dataset", lambda params: dataset)
    monkeypatch.setattr("src.modal.simulation._build_simulation", fake_build_simulation)
    monkeypatch.setattr(
        "src.modal.simulation.SimulationOutputBuilder",
        FakeSimulationOutputBuilder,
    )

    result = _run_simulation_impl_core(
        {
            "country": "us",
            "baseline": {"gov.test.parameter": {"2026-01-01.2100-12-31": 1}},
            "reform": {"gov.test.parameter": {"2026-01-01.2100-12-31": 2}},
        }
    )

    assert result == CURRENT_SINGLE_YEAR_MACRO_RESULT
    assert build_calls[0][2] == {"gov.test.parameter": {"2026-01-01": 1}}
    assert build_calls[1][2] == {"gov.test.parameter": {"2026-01-01": 2}}
    assert builder_calls == [
        {
            "country": "us",
            "simulation_params": {
                "country": "us",
                "baseline": {"gov.test.parameter": {"2026-01-01.2100-12-31": 1}},
                "reform": {"gov.test.parameter": {"2026-01-01.2100-12-31": 2}},
            },
            "country_module": country_module,
            "dataset": dataset,
            "baseline": baseline_simulation,
            "reform": reform_simulation,
        }
    ]


def test_builder_budgetary_impact_uses_materialized_columns_and_uk_state_tax_zero():
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

    us_budget = _simulation_output_builder(
        "us", baseline, reform
    )._build_budgetary_impact()
    uk_budget = _simulation_output_builder(
        "uk", baseline, reform
    )._build_budgetary_impact()

    assert isinstance(us_budget, BudgetaryImpact)
    assert us_budget.model_dump(mode="json") == {
        "tax_revenue_impact": 15.0,
        "state_tax_revenue_impact": 5.0,
        "benefit_spending_impact": -3.0,
        "budgetary_impact": 18.0,
        "households": 3.0,
        "baseline_net_income": 300.0,
    }
    assert uk_budget.state_tax_revenue_impact == 0.0


def test_builder_budgetary_impact_propagates_required_calculation_errors(monkeypatch):
    baseline, reform = _macro_baseline_reform()

    def fail_change_output_variable(*args, **kwargs):
        raise RuntimeError("household_tax missing")

    monkeypatch.setattr(
        "src.modal.simulation_output_builder._change_output_variable",
        fail_change_output_variable,
    )

    with pytest.raises(RuntimeError, match="household_tax missing"):
        _simulation_output_builder("us", baseline, reform)._build_budgetary_impact()


def test_uk_constituency_impact_uses_policyengine_output_function(monkeypatch):
    baseline = object()
    reform = object()
    expected = [{"constituency_code": "E14000530"}]

    def fake_output_module_function(module_name, name):
        assert module_name == "constituency_impact"
        assert name == "compute_uk_constituency_impacts"

        def compute(baseline_simulation, reform_simulation):
            assert baseline_simulation is baseline
            assert reform_simulation is reform
            return SimpleNamespace(constituency_results=expected)

        return compute

    monkeypatch.setattr(
        "src.modal.simulation_output_builder._output_module_function",
        fake_output_module_function,
    )

    assert (
        _simulation_output_builder("uk", baseline, reform)
        ._build_uk_constituency_impact()
        .root
        == expected
    )
    assert (
        _simulation_output_builder(
            "us", baseline, reform
        )._build_uk_constituency_impact()
        is None
    )


def test_uk_local_authority_impact_uses_policyengine_output_function(monkeypatch):
    baseline = object()
    reform = object()
    expected = [{"local_authority_code": "E06000001"}]

    def fake_output_module_function(module_name, name):
        assert module_name == "local_authority_impact"
        assert name == "compute_uk_local_authority_impacts"

        def compute(baseline_simulation, reform_simulation):
            assert baseline_simulation is baseline
            assert reform_simulation is reform
            return SimpleNamespace(local_authority_results=expected)

        return compute

    monkeypatch.setattr(
        "src.modal.simulation_output_builder._output_module_function",
        fake_output_module_function,
    )

    assert (
        _simulation_output_builder("uk", baseline, reform)
        ._build_uk_local_authority_impact()
        .root
        == expected
    )
    assert (
        _simulation_output_builder(
            "us", baseline, reform
        )._build_uk_local_authority_impact()
        is None
    )
