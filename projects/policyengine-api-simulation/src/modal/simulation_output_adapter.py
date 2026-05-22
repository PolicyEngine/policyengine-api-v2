"""Adapt PolicyEngine v4 macro outputs to the existing simulation API shape."""

from __future__ import annotations

import math
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import Any

from src.modal.simulation_macro_output import (
    AgePovertyOutput,
    BaselineReformValue,
    BudgetaryImpact,
    BudgetaryOutput,
    DecileOutput,
    DetailedBudgetOutput,
    DetailedBudgetProgramOutput,
    GeographicImpactOutput,
    GenderPovertyOutput,
    InequalityOutput,
    IntraDecileOutput,
    LaborSupplyResponseOutput,
    PovertyByGenderOutput,
    PovertyByRaceOutput,
    PovertyOutput,
    RacePovertyOutput,
    SingleYearMacroOutput,
)

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


def build_geographic_impact_output(value: Any) -> GeographicImpactOutput | None:
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


def build_budgetary_output(
    budget: Mapping[str, Any] | BudgetaryImpact,
) -> BudgetaryOutput:
    if isinstance(budget, BudgetaryImpact):
        return budget
    return BudgetaryImpact(
        tax_revenue_impact=_number(budget.get("tax_revenue_impact")),
        state_tax_revenue_impact=_number(budget.get("state_tax_revenue_impact")),
        benefit_spending_impact=_number(budget.get("benefit_spending_impact")),
        budgetary_impact=_number(budget.get("budgetary_impact")),
        households=_number(budget.get("households")),
        baseline_net_income=_number(budget.get("baseline_net_income")),
    )


def build_detailed_budget_output(
    collection: Any,
) -> DetailedBudgetOutput:
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


def build_decile_output(collection: Any) -> DecileOutput:
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


def build_intra_decile_output(collection: Any) -> IntraDecileOutput:
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


def build_poverty_output(
    country: str,
    *,
    baseline: Any,
    reform: Any,
    baseline_by_age: Any,
    reform_by_age: Any,
) -> PovertyOutput:
    if isinstance(baseline, PovertyOutput):
        return baseline
    result = {"poverty": _empty_age_poverty(), "deep_poverty": _empty_age_poverty()}
    _fill_poverty_block(
        country=country,
        output=result,
        baseline_records=_collection_records(baseline),
        reform_records=_collection_records(reform),
        default_group="all",
    )
    _fill_poverty_block(
        country=country,
        output=result,
        baseline_records=_collection_records(baseline_by_age),
        reform_records=_collection_records(reform_by_age),
        default_group="all",
    )
    return PovertyOutput(
        poverty=_age_poverty_output(result["poverty"]),
        deep_poverty=_age_poverty_output(result["deep_poverty"]),
    )


def build_poverty_by_gender_output(
    country: str,
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
        country=country,
        output=result,
        baseline_records=_collection_records(baseline_by_gender),
        reform_records=_collection_records(reform_by_gender),
        default_group="all",
    )
    return PovertyByGenderOutput(
        poverty=_gender_poverty_output(result["poverty"]),
        deep_poverty=_gender_poverty_output(result["deep_poverty"]),
    )


def build_poverty_by_race_output(
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


def build_inequality_output(baseline: Any, reform: Any) -> InequalityOutput:
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


def build_labor_supply_response_output(
    analysis: Any,
) -> LaborSupplyResponseOutput | None:
    if isinstance(analysis, LaborSupplyResponseOutput):
        return analysis
    output = _output_model_dump(getattr(analysis, "labor_supply_response", None))
    return LaborSupplyResponseOutput(output) if isinstance(output, dict) else None


@dataclass
class SingleYearMacroOutputBuilder:
    country: str
    model_version: str
    data_version: str
    budget: Mapping[str, Any] | BudgetaryImpact
    analysis: Any
    baseline_poverty_by_age: Any = None
    reform_poverty_by_age: Any = None
    baseline_poverty_by_gender: Any = None
    reform_poverty_by_gender: Any = None
    baseline_poverty_by_race: Any = None
    reform_poverty_by_race: Any = None
    intra_decile: Any = None
    congressional_district_impact: Any = None
    constituency_impact: Any = None
    local_authority_impact: Any = None

    def __post_init__(self) -> None:
        self.country = self.country.lower()

    def build(self) -> SingleYearMacroOutput:
        return SingleYearMacroOutput(
            model_version=self.model_version,
            data_version=self.data_version,
            budget=self._build_budgetary_impact(),
            detailed_budget=self._build_detailed_budget(),
            decile=self._build_decile(),
            inequality=self._build_inequality(),
            poverty=self._build_poverty(),
            poverty_by_gender=self._build_poverty_by_gender(),
            poverty_by_race=self._build_poverty_by_race(),
            intra_decile=self._build_intra_decile(),
            wealth_decile=self._build_wealth_decile(),
            intra_wealth_decile=self._build_intra_wealth_decile(),
            labor_supply_response=self._build_labor_supply_response(),
            constituency_impact=self._build_constituency_impact(),
            local_authority_impact=self._build_local_authority_impact(),
            congressional_district_impact=self._build_congressional_district_impact(),
            cliff_impact=None,
        )

    def serialize(self) -> dict[str, Any]:
        return self.build().model_dump(mode="json")

    def _build_budgetary_impact(self) -> BudgetaryImpact:
        return build_budgetary_output(self.budget)

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

    def _build_poverty(self) -> PovertyOutput:
        return build_poverty_output(
            self.country,
            baseline=getattr(self.analysis, "baseline_poverty", None),
            reform=getattr(self.analysis, "reform_poverty", None),
            baseline_by_age=self.baseline_poverty_by_age,
            reform_by_age=self.reform_poverty_by_age,
        )

    def _build_poverty_by_gender(self) -> PovertyByGenderOutput:
        return build_poverty_by_gender_output(
            self.country,
            baseline_by_gender=self.baseline_poverty_by_gender,
            reform_by_gender=self.reform_poverty_by_gender,
        )

    def _build_poverty_by_race(self) -> PovertyByRaceOutput | None:
        if self.country != "us":
            return None
        return build_poverty_by_race_output(
            baseline_by_race=self.baseline_poverty_by_race,
            reform_by_race=self.reform_poverty_by_race,
        )

    def _build_intra_decile(self) -> IntraDecileOutput:
        return build_intra_decile_output(self.intra_decile)

    def _build_wealth_decile(self) -> DecileOutput | None:
        if self.country != "uk":
            return None
        return build_decile_output(
            getattr(self.analysis, "wealth_decile_impacts", None)
        )

    def _build_intra_wealth_decile(self) -> IntraDecileOutput | None:
        if self.country != "uk":
            return None
        return build_intra_decile_output(
            getattr(self.analysis, "intra_wealth_decile_impacts", None)
        )

    def _build_labor_supply_response(self) -> LaborSupplyResponseOutput | None:
        return build_labor_supply_response_output(self.analysis)

    def _build_constituency_impact(self) -> GeographicImpactOutput | None:
        return build_geographic_impact_output(self.constituency_impact)

    def _build_local_authority_impact(self) -> GeographicImpactOutput | None:
        return build_geographic_impact_output(self.local_authority_impact)

    def _build_congressional_district_impact(self) -> GeographicImpactOutput | None:
        return build_geographic_impact_output(self.congressional_district_impact)


def build_single_year_macro_output(
    *,
    country: str,
    model_version: str,
    data_version: str,
    budget: Mapping[str, Any] | BudgetaryImpact,
    analysis: Any,
    baseline_poverty_by_age: Any = None,
    reform_poverty_by_age: Any = None,
    baseline_poverty_by_gender: Any = None,
    reform_poverty_by_gender: Any = None,
    baseline_poverty_by_race: Any = None,
    reform_poverty_by_race: Any = None,
    intra_decile: Any = None,
    congressional_district_impact: Any = None,
    constituency_impact: Any = None,
    local_authority_impact: Any = None,
) -> SingleYearMacroOutput:
    """Build the schema-first single-year macro output."""
    return SingleYearMacroOutputBuilder(
        country=country,
        model_version=model_version,
        data_version=data_version,
        budget=budget,
        analysis=analysis,
        baseline_poverty_by_age=baseline_poverty_by_age,
        reform_poverty_by_age=reform_poverty_by_age,
        baseline_poverty_by_gender=baseline_poverty_by_gender,
        reform_poverty_by_gender=reform_poverty_by_gender,
        baseline_poverty_by_race=baseline_poverty_by_race,
        reform_poverty_by_race=reform_poverty_by_race,
        intra_decile=intra_decile,
        congressional_district_impact=congressional_district_impact,
        constituency_impact=constituency_impact,
        local_authority_impact=local_authority_impact,
    ).build()


def adapt_analysis_to_legacy_macro_output(
    *,
    country: str,
    model_version: str,
    data_version: str,
    budget: Mapping[str, Any] | BudgetaryImpact,
    analysis: Any,
    baseline_poverty_by_age: Any = None,
    reform_poverty_by_age: Any = None,
    baseline_poverty_by_gender: Any = None,
    reform_poverty_by_gender: Any = None,
    baseline_poverty_by_race: Any = None,
    reform_poverty_by_race: Any = None,
    intra_decile: Any = None,
    congressional_district_impact: Any = None,
    constituency_impact: Any = None,
    local_authority_impact: Any = None,
) -> dict[str, Any]:
    """Return the legacy single-year macro result expected by API callers."""
    return SingleYearMacroOutputBuilder(
        country=country,
        model_version=model_version,
        data_version=data_version,
        budget=budget,
        analysis=analysis,
        baseline_poverty_by_age=baseline_poverty_by_age,
        reform_poverty_by_age=reform_poverty_by_age,
        baseline_poverty_by_gender=baseline_poverty_by_gender,
        reform_poverty_by_gender=reform_poverty_by_gender,
        baseline_poverty_by_race=baseline_poverty_by_race,
        reform_poverty_by_race=reform_poverty_by_race,
        intra_decile=intra_decile,
        congressional_district_impact=congressional_district_impact,
        constituency_impact=constituency_impact,
        local_authority_impact=local_authority_impact,
    ).serialize()
