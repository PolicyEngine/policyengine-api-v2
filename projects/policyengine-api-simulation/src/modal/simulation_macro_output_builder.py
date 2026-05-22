"""Build and serialize the runtime simulation macro output."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from importlib import import_module
from typing import Any

from src.modal.release_bundle import get_country_release_bundle
from src.modal.simulation_macro_output import (
    BudgetaryImpact,
    DecileOutput,
    DetailedBudgetOutput,
    GeographicImpactOutput,
    InequalityOutput,
    IntraDecileOutput,
    LaborSupplyResponseOutput,
    PovertyModuleOutputs,
    SingleYearMacroOutput,
)
from src.modal.simulation_output_adapter import (
    build_decile_output,
    build_detailed_budget_output,
    build_geographic_impact_output,
    build_inequality_output,
    build_intra_decile_output,
    build_labor_supply_response_output,
    build_poverty_by_gender_output,
    build_poverty_by_race_output,
    build_poverty_output,
)

logger = logging.getLogger(__name__)


def _entity_data(simulation, entity: str):
    if simulation.output_dataset is None or simulation.output_dataset.data is None:
        simulation.ensure()
    return getattr(simulation.output_dataset.data, entity)


def _sum_output_variable(simulation, variable: str, entity: str) -> float:
    data = _entity_data(simulation, entity)
    if variable in data.columns:
        return float(data[variable].sum())

    from policyengine.outputs import Aggregate, AggregateType

    output = Aggregate(
        simulation=simulation,
        variable=variable,
        entity=entity,
        aggregate_type=AggregateType.SUM,
    )
    output.run()
    return float(output.result)


def _try_sum_output_variable(simulation, variable: str, entity: str) -> float:
    try:
        return _sum_output_variable(simulation, variable, entity)
    except Exception:
        logger.warning("Unable to calculate sum for %s", variable, exc_info=True)
        return 0.0


def _change_output_variable(baseline, reform, variable: str, entity: str) -> float:
    baseline_data = _entity_data(baseline, entity)
    reform_data = _entity_data(reform, entity)
    if variable in baseline_data.columns and variable in reform_data.columns:
        return float((reform_data[variable] - baseline_data[variable]).sum())

    from policyengine.outputs import ChangeAggregate, ChangeAggregateType

    output = ChangeAggregate(
        baseline_simulation=baseline,
        reform_simulation=reform,
        variable=variable,
        entity=entity,
        aggregate_type=ChangeAggregateType.SUM,
    )
    output.run()
    return float(output.result)


def _try_change_output_variable(baseline, reform, variable: str, entity: str) -> float:
    try:
        return _change_output_variable(baseline, reform, variable, entity)
    except Exception:
        logger.warning("Unable to calculate change for %s", variable, exc_info=True)
        return 0.0


def _output_module_function(module_name: str, name: str):
    module = import_module(f"policyengine.outputs.{module_name}")
    return getattr(module, name)


def _poverty_module_function(name: str):
    return _output_module_function("poverty", name)


def _try_compute_output(label: str, fn, *args, **kwargs):
    try:
        return fn(*args, **kwargs)
    except Exception:
        logger.warning("Unable to calculate %s", label, exc_info=True)
        return None


@dataclass
class SimulationMacroOutputBuilder:
    country: str
    simulation_params: dict[str, Any]
    country_module: Any
    dataset: Any
    baseline: Any
    reform: Any
    analysis: Any

    def __post_init__(self) -> None:
        self.country = self.country.lower()

    def build(self) -> SingleYearMacroOutput:
        poverty_outputs = self._build_poverty_outputs()
        wealth_decile = getattr(self.analysis, "wealth_decile_impacts", None)
        intra_wealth_decile = getattr(
            self.analysis, "intra_wealth_decile_impacts", None
        )

        return SingleYearMacroOutput(
            model_version=self._model_version(),
            data_version=self._data_version(),
            budget=self._build_budgetary_impact(),
            detailed_budget=self._build_detailed_budget(),
            decile=self._build_decile(),
            inequality=self._build_inequality(),
            poverty=poverty_outputs.poverty,
            poverty_by_gender=poverty_outputs.poverty_by_gender,
            poverty_by_race=poverty_outputs.poverty_by_race,
            intra_decile=self._build_intra_decile_output(),
            wealth_decile=self._build_wealth_decile(wealth_decile),
            intra_wealth_decile=self._build_intra_wealth_decile(intra_wealth_decile),
            labor_supply_response=self._build_labor_supply_response(),
            congressional_district_impact=(self._build_congressional_district_impact()),
            constituency_impact=self._build_uk_constituency_impact(),
            local_authority_impact=self._build_uk_local_authority_impact(),
            cliff_impact=None,
        )

    def serialize(self) -> dict[str, Any]:
        return self.build().model_dump(mode="json")

    def _build_detailed_budget(self) -> DetailedBudgetOutput:
        return build_detailed_budget_output(
            getattr(self.analysis, "program_statistics", None)
        )

    def _build_decile(self) -> DecileOutput:
        return build_decile_output(getattr(self.analysis, "decile_impacts", None))

    def _build_inequality(self) -> InequalityOutput:
        return build_inequality_output(
            getattr(self.analysis, "baseline_inequality", None),
            getattr(self.analysis, "reform_inequality", None),
        )

    def _build_budgetary_impact(self) -> BudgetaryImpact:
        tax_revenue_impact = _try_change_output_variable(
            self.baseline, self.reform, "household_tax", entity="household"
        )
        benefit_spending_impact = _try_change_output_variable(
            self.baseline, self.reform, "household_benefits", entity="household"
        )
        state_tax_revenue_impact = (
            _try_change_output_variable(
                self.baseline,
                self.reform,
                "household_state_income_tax",
                entity="household",
            )
            if self.country == "us"
            else 0.0
        )

        return BudgetaryImpact(
            tax_revenue_impact=tax_revenue_impact,
            state_tax_revenue_impact=state_tax_revenue_impact,
            benefit_spending_impact=benefit_spending_impact,
            budgetary_impact=tax_revenue_impact - benefit_spending_impact,
            households=_try_sum_output_variable(
                self.baseline, "household_weight", entity="household"
            ),
            baseline_net_income=_try_sum_output_variable(
                self.baseline, "household_net_income", entity="household"
            ),
        )

    def _build_poverty_outputs(self) -> PovertyModuleOutputs:
        prefix = "us" if self.country == "us" else "uk"
        baseline_poverty_by_age = _try_compute_output(
            "baseline poverty by age",
            _poverty_module_function(f"calculate_{prefix}_poverty_by_age"),
            self.baseline,
        )
        reform_poverty_by_age = _try_compute_output(
            "reform poverty by age",
            _poverty_module_function(f"calculate_{prefix}_poverty_by_age"),
            self.reform,
        )
        baseline_poverty_by_gender = _try_compute_output(
            "baseline poverty by gender",
            _poverty_module_function(f"calculate_{prefix}_poverty_by_gender"),
            self.baseline,
        )
        reform_poverty_by_gender = _try_compute_output(
            "reform poverty by gender",
            _poverty_module_function(f"calculate_{prefix}_poverty_by_gender"),
            self.reform,
        )
        baseline_poverty_by_race = None
        reform_poverty_by_race = None
        if self.country == "us":
            baseline_poverty_by_race = _try_compute_output(
                "baseline poverty by race",
                _poverty_module_function("calculate_us_poverty_by_race"),
                self.baseline,
            )
            reform_poverty_by_race = _try_compute_output(
                "reform poverty by race",
                _poverty_module_function("calculate_us_poverty_by_race"),
                self.reform,
            )
        return PovertyModuleOutputs(
            poverty=build_poverty_output(
                self.country,
                baseline=getattr(self.analysis, "baseline_poverty", None),
                reform=getattr(self.analysis, "reform_poverty", None),
                baseline_by_age=baseline_poverty_by_age,
                reform_by_age=reform_poverty_by_age,
            ),
            poverty_by_gender=build_poverty_by_gender_output(
                self.country,
                baseline_by_gender=baseline_poverty_by_gender,
                reform_by_gender=reform_poverty_by_gender,
            ),
            poverty_by_race=(
                build_poverty_by_race_output(
                    baseline_by_race=baseline_poverty_by_race,
                    reform_by_race=reform_poverty_by_race,
                )
                if self.country == "us"
                else None
            ),
        )

    def _build_intra_decile_output(self) -> IntraDecileOutput:
        from policyengine.outputs.intra_decile_impact import (
            compute_intra_decile_impacts,
        )

        collection = _try_compute_output(
            "intra-decile impacts",
            compute_intra_decile_impacts,
            self.baseline,
            self.reform,
            income_variable="household_net_income",
            entity="household",
        )
        return build_intra_decile_output(collection)

    def _build_wealth_decile(self, wealth_decile) -> DecileOutput | None:
        if self.country != "uk":
            return None
        return build_decile_output(wealth_decile)

    def _build_intra_wealth_decile(
        self, intra_wealth_decile
    ) -> IntraDecileOutput | None:
        if self.country != "uk":
            return None
        return build_intra_decile_output(intra_wealth_decile)

    def _build_labor_supply_response(self) -> LaborSupplyResponseOutput | None:
        return build_labor_supply_response_output(self.analysis)

    def _build_congressional_district_impact(
        self,
    ) -> GeographicImpactOutput | None:
        if self.country != "us":
            return None

        from policyengine.outputs.congressional_district_impact import (
            compute_us_congressional_district_impacts,
        )

        impact = _try_compute_output(
            "congressional district impacts",
            compute_us_congressional_district_impacts,
            self.baseline,
            self.reform,
        )
        return build_geographic_impact_output(
            getattr(impact, "district_results", None) if impact is not None else None
        )

    def _build_uk_constituency_impact(self) -> GeographicImpactOutput | None:
        if self.country != "uk":
            return None

        impact = _try_compute_output(
            "constituency impacts",
            _output_module_function(
                "constituency_impact", "compute_uk_constituency_impacts"
            ),
            self.baseline,
            self.reform,
        )
        if impact is None:
            return None
        return build_geographic_impact_output(
            getattr(impact, "constituency_results", None)
        )

    def _build_uk_local_authority_impact(self) -> GeographicImpactOutput | None:
        if self.country != "uk":
            return None

        impact = _try_compute_output(
            "local authority impacts",
            _output_module_function(
                "local_authority_impact", "compute_uk_local_authority_impacts"
            ),
            self.baseline,
            self.reform,
        )
        if impact is None:
            return None
        return build_geographic_impact_output(
            getattr(impact, "local_authority_results", None)
        )

    def _model_version(self) -> str:
        return str(getattr(self.country_module.model, "version", ""))

    def _data_version(self) -> str:
        if self.simulation_params.get("data_version"):
            return str(self.simulation_params["data_version"])
        try:
            return get_country_release_bundle(self.country).data_version
        except ValueError:
            pass
        metadata = getattr(self.dataset, "metadata", {}) or {}
        for key in ("data_version", "version"):
            value = metadata.get(key)
            if value is not None:
                return str(value)
        return ""
