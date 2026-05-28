"""Build and serialize the runtime simulation macro output."""

from __future__ import annotations

import logging
import math
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from importlib import import_module
from typing import Any

from policyengine_api_simulation.release_bundle import get_country_release_bundle
from policyengine_api_simulation.simulation_macro_output import (
    AgePovertyOutput,
    BaselineReformValue,
    BudgetaryImpact,
    CliffImpactInSimulation,
    CliffImpactOutput,
    DecileOutput,
    DetailedBudgetOutput,
    DetailedBudgetProgramOutput,
    GeographicImpactOutput,
    GenderPovertyOutput,
    InequalityOutput,
    IntraDecileOutput,
    LaborSupplyResponseOutput,
    PovertyModuleOutputs,
    PovertyByGenderOutput,
    PovertyByRaceOutput,
    PovertyOutput,
    RacePovertyOutput,
    SingleYearMacroOutput,
)

logger = logging.getLogger(__name__)

INTRA_DECILE_COLUMNS = {
    "Lose more than 5%": "lose_more_than_5pct",
    "Lose less than 5%": "lose_less_than_5pct",
    "No change": "no_change",
    "Gain less than 5%": "gain_less_than_5pct",
    "Gain more than 5%": "gain_more_than_5pct",
}

US_POVERTY_TYPES = {
    "spm": "poverty",
    "spm_deep": "deep_poverty",
}

UK_POVERTY_TYPES = {
    "relative_bhc": "poverty",
    "absolute_bhc": "deep_poverty",
}


def _number(value: Any, default: float = 0.0) -> float:
    if value is None:
        return default
    try:
        result = float(value)
    except (TypeError, ValueError):
        return default
    if math.isnan(result) or math.isinf(result):
        return default
    return result


def _collection_records(collection: Any) -> list[dict[str, Any]]:
    if collection is None:
        return []
    dataframe = getattr(collection, "dataframe", None)
    if dataframe is not None:
        return list(dataframe.to_dict("records"))
    if isinstance(collection, list):
        return [dict(item) for item in collection if isinstance(item, Mapping)]
    return []


def _output_model_dump(value: Any) -> Any:
    if value is None:
        return None
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")
    if isinstance(value, Mapping):
        return dict(value)
    return None


def _empty_baseline_reform_value() -> dict[str, float]:
    return {"baseline": 0.0, "reform": 0.0}


def _empty_age_poverty() -> dict[str, dict[str, float]]:
    return {
        "child": _empty_baseline_reform_value(),
        "adult": _empty_baseline_reform_value(),
        "senior": _empty_baseline_reform_value(),
        "all": _empty_baseline_reform_value(),
    }


def _empty_gender_poverty() -> dict[str, dict[str, float]]:
    return {
        "male": _empty_baseline_reform_value(),
        "female": _empty_baseline_reform_value(),
    }


def _poverty_type(country: str, row: Mapping[str, Any]) -> str | None:
    poverty_type = str(row.get("poverty_type") or "").lower()
    if country == "us":
        return US_POVERTY_TYPES.get(poverty_type)
    return UK_POVERTY_TYPES.get(poverty_type)


def _fill_poverty_block(
    *,
    country: str,
    output: dict[str, dict[str, dict[str, float]]],
    baseline_records: Iterable[Mapping[str, Any]],
    reform_records: Iterable[Mapping[str, Any]],
    default_group: str,
) -> None:
    for side, records in (("baseline", baseline_records), ("reform", reform_records)):
        for row in records:
            poverty_type = _poverty_type(country, row)
            if poverty_type is None:
                continue
            if poverty_type not in output:
                continue
            group = str(row.get("filter_group") or default_group).lower()
            if group not in output[poverty_type]:
                continue
            output[poverty_type][group][side] = _number(row.get("rate"))


def _age_poverty_output(values: dict[str, dict[str, float]]) -> AgePovertyOutput:
    return AgePovertyOutput(
        child=BaselineReformValue(**values["child"]),
        adult=BaselineReformValue(**values["adult"]),
        senior=BaselineReformValue(**values["senior"]),
        all=BaselineReformValue(**values["all"]),
    )


def _gender_poverty_output(
    values: dict[str, dict[str, float]],
) -> GenderPovertyOutput:
    return GenderPovertyOutput(
        male=BaselineReformValue(**values["male"]),
        female=BaselineReformValue(**values["female"]),
    )


def _race_poverty_output(values: dict[str, dict[str, float]]) -> RacePovertyOutput:
    return RacePovertyOutput(
        white=BaselineReformValue(**values["white"]),
        black=BaselineReformValue(**values["black"]),
        hispanic=BaselineReformValue(**values["hispanic"]),
        other=BaselineReformValue(**values["other"]),
    )


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
class SimulationOutputBuilder:
    country: str
    simulation_params: dict[str, Any]
    country_module: Any
    dataset: Any
    baseline: Any
    reform: Any
    resolved_data_version: str | None = None
    _analysis: Any = field(default=None, init=False)

    def __post_init__(self) -> None:
        self.country = self.country.lower()

    @property
    def analysis(self) -> Any:
        if self._analysis is None:
            self._analysis = self.country_module.economic_impact_analysis(
                self.baseline,
                self.reform,
                include_cliff_impacts=self._include_cliff_impacts(),
            )
        return self._analysis

    def _include_cliff_impacts(self) -> bool:
        return self.simulation_params.get("include_cliffs") is True

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
            cliff_impact=self._build_cliff_impact(),
        )

    def serialize(self) -> dict[str, Any]:
        return self.build().model_dump(mode="json")

    def _build_detailed_budget(self) -> DetailedBudgetOutput:
        collection = getattr(self.analysis, "program_statistics", None)
        if isinstance(collection, DetailedBudgetOutput):
            return collection
        detailed_budget: dict[str, DetailedBudgetProgramOutput] = {}
        for row in _collection_records(collection):
            program_name = row.get("program_name")
            if not program_name:
                continue
            baseline = _number(row.get("baseline_total"))
            reform = _number(row.get("reform_total"))
            detailed_budget[str(program_name)] = DetailedBudgetProgramOutput(
                baseline=baseline,
                reform=reform,
                difference=_number(row.get("change"), reform - baseline),
            )
        return DetailedBudgetOutput(detailed_budget)

    def _build_decile(self) -> DecileOutput:
        return self._build_decile_output(getattr(self.analysis, "decile_impacts", None))

    def _build_inequality(self) -> InequalityOutput:
        baseline = getattr(self.analysis, "baseline_inequality", None)
        reform = getattr(self.analysis, "reform_inequality", None)
        if isinstance(baseline, InequalityOutput):
            return baseline
        return InequalityOutput(
            gini=BaselineReformValue(
                baseline=_number(getattr(baseline, "gini", None)),
                reform=_number(getattr(reform, "gini", None)),
            ),
            top_10_pct_share=BaselineReformValue(
                baseline=_number(getattr(baseline, "top_10_share", None)),
                reform=_number(getattr(reform, "top_10_share", None)),
            ),
            top_1_pct_share=BaselineReformValue(
                baseline=_number(getattr(baseline, "top_1_share", None)),
                reform=_number(getattr(reform, "top_1_share", None)),
            ),
        )

    def _build_budgetary_impact(self) -> BudgetaryImpact:
        tax_revenue_impact = _change_output_variable(
            self.baseline, self.reform, "household_tax", entity="household"
        )
        benefit_spending_impact = _change_output_variable(
            self.baseline, self.reform, "household_benefits", entity="household"
        )
        state_tax_revenue_impact = (
            _change_output_variable(
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
            households=_sum_output_variable(
                self.baseline, "household_weight", entity="household"
            ),
            baseline_net_income=_sum_output_variable(
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
            poverty=self._build_poverty_output(
                baseline=getattr(self.analysis, "baseline_poverty", None),
                reform=getattr(self.analysis, "reform_poverty", None),
                baseline_by_age=baseline_poverty_by_age,
                reform_by_age=reform_poverty_by_age,
            ),
            poverty_by_gender=self._build_poverty_by_gender_output(
                baseline_by_gender=baseline_poverty_by_gender,
                reform_by_gender=reform_poverty_by_gender,
            ),
            poverty_by_race=(
                self._build_poverty_by_race_output(
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
        return self._build_intra_decile_output_from_collection(collection)

    def _build_wealth_decile(self, wealth_decile) -> DecileOutput | None:
        if self.country != "uk":
            return None
        return self._build_decile_output(wealth_decile)

    def _build_intra_wealth_decile(
        self, intra_wealth_decile
    ) -> IntraDecileOutput | None:
        if self.country != "uk":
            return None
        return self._build_intra_decile_output_from_collection(intra_wealth_decile)

    def _build_labor_supply_response(self) -> LaborSupplyResponseOutput | None:
        labor_supply_response = getattr(self.analysis, "labor_supply_response", None)
        if isinstance(labor_supply_response, LaborSupplyResponseOutput):
            return labor_supply_response
        output = _output_model_dump(labor_supply_response)
        return LaborSupplyResponseOutput(output) if isinstance(output, dict) else None

    def _build_cliff_impact(self) -> CliffImpactOutput | None:
        cliff_impact = getattr(self.analysis, "cliff_impact", None)
        if isinstance(cliff_impact, CliffImpactOutput):
            return cliff_impact
        output = _output_model_dump(cliff_impact)
        if not isinstance(output, Mapping):
            return None
        return CliffImpactOutput(
            baseline=CliffImpactInSimulation(**output["baseline"]),
            reform=CliffImpactInSimulation(**output["reform"]),
        )

    def _build_geographic_impact_output(
        self, value: Any
    ) -> GeographicImpactOutput | None:
        if isinstance(value, GeographicImpactOutput):
            return value
        records = _output_model_dump(value)
        if isinstance(records, list):
            return GeographicImpactOutput(
                [dict(item) for item in records if isinstance(item, Mapping)]
            )
        if isinstance(value, list):
            return GeographicImpactOutput(
                [dict(item) for item in value if isinstance(item, Mapping)]
            )
        return None

    def _build_decile_output(self, collection: Any) -> DecileOutput:
        if isinstance(collection, DecileOutput):
            return collection
        average: dict[str, float] = {}
        relative: dict[str, float] = {}
        for row in sorted(
            _collection_records(collection),
            key=lambda item: _number(item.get("decile")),
        ):
            decile = int(_number(row.get("decile")))
            if decile <= 0:
                continue
            key = str(decile)
            average[key] = _number(row.get("absolute_change"))
            relative[key] = _number(row.get("relative_change"))
        return DecileOutput(average=average, relative=relative)

    def _build_intra_decile_output_from_collection(
        self, collection: Any
    ) -> IntraDecileOutput:
        if isinstance(collection, IntraDecileOutput):
            return collection
        deciles: dict[str, list[float]] = {label: [] for label in INTRA_DECILE_COLUMNS}
        all_values: dict[str, float] = {label: 0.0 for label in INTRA_DECILE_COLUMNS}
        rows = [
            row
            for row in sorted(
                _collection_records(collection),
                key=lambda item: _number(item.get("decile")),
            )
            if int(_number(row.get("decile"))) > 0
        ]

        for label, column in INTRA_DECILE_COLUMNS.items():
            values = [_number(row.get(column)) for row in rows]
            deciles[label] = values
            all_values[label] = sum(values) / len(values) if values else 0.0
        return IntraDecileOutput(deciles=deciles, all=all_values)

    def _build_poverty_output(
        self,
        *,
        baseline: Any,
        reform: Any,
        baseline_by_age: Any,
        reform_by_age: Any,
    ) -> PovertyOutput:
        if isinstance(baseline, PovertyOutput):
            return baseline
        result = {
            "poverty": _empty_age_poverty(),
            "deep_poverty": _empty_age_poverty(),
        }
        _fill_poverty_block(
            country=self.country,
            output=result,
            baseline_records=_collection_records(baseline),
            reform_records=_collection_records(reform),
            default_group="all",
        )
        _fill_poverty_block(
            country=self.country,
            output=result,
            baseline_records=_collection_records(baseline_by_age),
            reform_records=_collection_records(reform_by_age),
            default_group="all",
        )
        return PovertyOutput(
            poverty=_age_poverty_output(result["poverty"]),
            deep_poverty=_age_poverty_output(result["deep_poverty"]),
        )

    def _build_poverty_by_gender_output(
        self,
        *,
        baseline_by_gender: Any,
        reform_by_gender: Any,
    ) -> PovertyByGenderOutput:
        if isinstance(baseline_by_gender, PovertyByGenderOutput):
            return baseline_by_gender
        result = {
            "poverty": _empty_gender_poverty(),
            "deep_poverty": _empty_gender_poverty(),
        }
        _fill_poverty_block(
            country=self.country,
            output=result,
            baseline_records=_collection_records(baseline_by_gender),
            reform_records=_collection_records(reform_by_gender),
            default_group="all",
        )
        return PovertyByGenderOutput(
            poverty=_gender_poverty_output(result["poverty"]),
            deep_poverty=_gender_poverty_output(result["deep_poverty"]),
        )

    def _build_poverty_by_race_output(
        self,
        *,
        baseline_by_race: Any,
        reform_by_race: Any,
    ) -> PovertyByRaceOutput:
        if isinstance(baseline_by_race, PovertyByRaceOutput):
            return baseline_by_race
        result = {
            "poverty": {
                "white": _empty_baseline_reform_value(),
                "black": _empty_baseline_reform_value(),
                "hispanic": _empty_baseline_reform_value(),
                "other": _empty_baseline_reform_value(),
            }
        }
        _fill_poverty_block(
            country="us",
            output=result,
            baseline_records=_collection_records(baseline_by_race),
            reform_records=_collection_records(reform_by_race),
            default_group="all",
        )
        return PovertyByRaceOutput(poverty=_race_poverty_output(result["poverty"]))

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
        return self._build_geographic_impact_output(
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
        return self._build_geographic_impact_output(
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
        return self._build_geographic_impact_output(
            getattr(impact, "local_authority_results", None)
        )

    def _model_version(self) -> str:
        return str(getattr(self.country_module.model, "version", ""))

    def _data_version(self) -> str:
        if self.resolved_data_version:
            return str(self.resolved_data_version)
        data = self.simulation_params.get("data")
        if isinstance(data, str) and "@" in data:
            revision = data.rsplit("@", maxsplit=1)[1]
            if revision:
                return revision
        if self.simulation_params.get("data_version"):
            return str(self.simulation_params["data_version"])
        metadata = getattr(self.dataset, "metadata", {}) or {}
        for key in ("data_version", "version"):
            value = metadata.get(key)
            if value is not None:
                return str(value)
        try:
            return get_country_release_bundle(self.country).data_version
        except ValueError:
            pass
        return ""
