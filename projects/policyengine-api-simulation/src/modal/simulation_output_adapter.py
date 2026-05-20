"""Adapt PolicyEngine v4 macro outputs to the existing simulation API shape."""

from __future__ import annotations

import math
from collections.abc import Iterable, Mapping
from typing import Any


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
    return value


def _detailed_budget(collection: Any) -> dict[str, dict[str, float]]:
    detailed_budget: dict[str, dict[str, float]] = {}
    for row in _collection_records(collection):
        program_name = row.get("program_name")
        if not program_name:
            continue
        baseline = _number(row.get("baseline_total"))
        reform = _number(row.get("reform_total"))
        detailed_budget[str(program_name)] = {
            "baseline": baseline,
            "reform": reform,
            "difference": _number(row.get("change"), reform - baseline),
        }
    return detailed_budget


def _decile_impact(collection: Any) -> dict[str, dict[str, float]]:
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
    return {"average": average, "relative": relative}


def _empty_intra_decile() -> dict[str, Any]:
    return {
        "deciles": {label: [] for label in INTRA_DECILE_COLUMNS},
        "all": {label: 0.0 for label in INTRA_DECILE_COLUMNS},
    }


def _intra_decile_impact(collection: Any) -> dict[str, Any]:
    result = _empty_intra_decile()
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
        result["deciles"][label] = values
        result["all"][label] = sum(values) / len(values) if values else 0.0
    return result


def _empty_age_poverty() -> dict[str, dict[str, float]]:
    return {
        "child": {"baseline": 0.0, "reform": 0.0},
        "adult": {"baseline": 0.0, "reform": 0.0},
        "senior": {"baseline": 0.0, "reform": 0.0},
        "all": {"baseline": 0.0, "reform": 0.0},
    }


def _empty_gender_poverty() -> dict[str, dict[str, float]]:
    return {
        "male": {"baseline": 0.0, "reform": 0.0},
        "female": {"baseline": 0.0, "reform": 0.0},
    }


def _empty_race_poverty() -> dict[str, dict[str, float]]:
    return {
        "white": {"baseline": 0.0, "reform": 0.0},
        "black": {"baseline": 0.0, "reform": 0.0},
        "hispanic": {"baseline": 0.0, "reform": 0.0},
        "other": {"baseline": 0.0, "reform": 0.0},
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


def _poverty_impact(
    country: str,
    *,
    baseline: Any,
    reform: Any,
    baseline_by_age: Any,
    reform_by_age: Any,
) -> dict[str, dict[str, dict[str, float]]]:
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
    return result


def _poverty_by_gender(
    country: str,
    *,
    baseline_by_gender: Any,
    reform_by_gender: Any,
) -> dict[str, dict[str, dict[str, float]]]:
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
    return result


def _poverty_by_race(
    *,
    baseline_by_race: Any,
    reform_by_race: Any,
) -> dict[str, dict[str, dict[str, float]]]:
    result = {"poverty": _empty_race_poverty()}
    _fill_poverty_block(
        country="us",
        output=result,
        baseline_records=_collection_records(baseline_by_race),
        reform_records=_collection_records(reform_by_race),
        default_group="all",
    )
    return result


def _inequality_impact(baseline: Any, reform: Any) -> dict[str, Any]:
    return {
        "gini": {
            "baseline": _number(getattr(baseline, "gini", None)),
            "reform": _number(getattr(reform, "gini", None)),
        },
        "top_10_pct_share": {
            "baseline": _number(getattr(baseline, "top_10_share", None)),
            "reform": _number(getattr(reform, "top_10_share", None)),
        },
        "top_1_pct_share": {
            "baseline": _number(getattr(baseline, "top_1_share", None)),
            "reform": _number(getattr(reform, "top_1_share", None)),
        },
    }


def adapt_analysis_to_legacy_macro_output(
    *,
    country: str,
    model_version: str,
    data_version: str,
    budget: dict[str, float],
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
    country = country.lower()
    wealth_decile = getattr(analysis, "wealth_decile_impacts", None)
    intra_wealth_decile = getattr(analysis, "intra_wealth_decile_impacts", None)

    return {
        "model_version": model_version,
        "data_version": data_version,
        "budget": budget,
        "detailed_budget": _detailed_budget(
            getattr(analysis, "program_statistics", None)
        ),
        "decile": _decile_impact(getattr(analysis, "decile_impacts", None)),
        "inequality": _inequality_impact(
            getattr(analysis, "baseline_inequality", None),
            getattr(analysis, "reform_inequality", None),
        ),
        "poverty": _poverty_impact(
            country,
            baseline=getattr(analysis, "baseline_poverty", None),
            reform=getattr(analysis, "reform_poverty", None),
            baseline_by_age=baseline_poverty_by_age,
            reform_by_age=reform_poverty_by_age,
        ),
        "poverty_by_gender": _poverty_by_gender(
            country,
            baseline_by_gender=baseline_poverty_by_gender,
            reform_by_gender=reform_poverty_by_gender,
        ),
        "poverty_by_race": (
            _poverty_by_race(
                baseline_by_race=baseline_poverty_by_race,
                reform_by_race=reform_poverty_by_race,
            )
            if country == "us"
            else None
        ),
        "intra_decile": _intra_decile_impact(intra_decile),
        "wealth_decile": _decile_impact(wealth_decile) if country == "uk" else None,
        "intra_wealth_decile": (
            _intra_decile_impact(intra_wealth_decile) if country == "uk" else None
        ),
        "labor_supply_response": _output_model_dump(
            getattr(analysis, "labor_supply_response", None)
        ),
        "constituency_impact": constituency_impact,
        "local_authority_impact": local_authority_impact,
        "congressional_district_impact": congressional_district_impact,
        "cliff_impact": None,
    }
