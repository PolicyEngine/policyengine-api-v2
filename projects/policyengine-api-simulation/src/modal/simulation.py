"""
Simulation implementation - pure logic with snapshotted imports.

This module has policyengine imports at module level so they are
captured in Modal's image snapshot. No Modal dependencies here.
"""

import contextlib
import importlib
import json
import logging
import os
import tempfile
from importlib.metadata import PackageNotFoundError, version
from typing import Any, Iterator

# policyengine.core is imported for every simulation. Without this guard,
# importing the package pulls both country modules into the process; a US run
# can then fail before it starts if UK private-data credentials are absent.
os.environ.setdefault("POLICYENGINE_SKIP_COUNTRY_IMPORTS", "1")

try:
    from src.modal.telemetry import split_internal_payload
except ModuleNotFoundError:
    from modal.telemetry import split_internal_payload

logger = logging.getLogger(__name__)


DEFAULT_YEAR = 2026
POVERTY_TYPES = ("poverty", "deep_poverty")
AGE_GROUPS = {
    "all": {},
    "child": {"filter_variable": "age", "filter_variable_leq": 17},
    "adult": {
        "filter_variable": "age",
        "filter_variable_geq": 18,
        "filter_variable_leq": 64,
    },
    "senior": {"filter_variable": "age", "filter_variable_geq": 65},
}
GENDER_GROUPS = {
    "male": {"filter_variable": "is_male", "filter_variable_eq": True},
    "female": {"filter_variable": "is_male", "filter_variable_eq": False},
}
RACE_GROUPS = {
    "white": {"filter_variable": "race", "filter_variable_eq": "WHITE"},
    "black": {"filter_variable": "race", "filter_variable_eq": "BLACK"},
    "hispanic": {"filter_variable": "race", "filter_variable_eq": "HISPANIC"},
    "other": {"filter_variable": "race", "filter_variable_eq": "OTHER"},
}
POVERTY_VARIABLES = {
    "us": {
        "poverty": "spm_unit_is_in_spm_poverty",
        "deep_poverty": "spm_unit_is_in_deep_spm_poverty",
    },
    "uk": {
        "poverty": "in_poverty_bhc",
        "deep_poverty": None,
    },
}
INTRA_DECILE_FIELDS = {
    "Gain less than 5%": "gain_less_than_5pct",
    "Gain more than 5%": "gain_more_than_5pct",
    "Lose less than 5%": "lose_less_than_5pct",
    "Lose more than 5%": "lose_more_than_5pct",
    "No change": "no_change",
}
DATASET_ALIASES = {
    "us": {
        "enhanced_cps": "enhanced_cps_2024",
        "enhanced_cps_2024": "enhanced_cps_2024",
        "gs://policyengine-us-data/enhanced_cps_2024.h5": "enhanced_cps_2024",
        "hf://policyengine/policyengine-us-data/enhanced_cps_2024.h5": "enhanced_cps_2024",
        "cps_small": "cps_small_2024",
        "cps_small_2024": "cps_small_2024",
    },
    "uk": {
        "enhanced_frs": "enhanced_frs_2023_24",
        "enhanced_frs_2023_24": "enhanced_frs_2023_24",
        "frs": "frs_2023_24",
        "frs_2023_24": "frs_2023_24",
    },
}


def _normalize_credentials_blob(creds_json: str) -> str:
    """Return the raw JSON blob, decoding the outer escape if present.

    The upstream Modal secret sometimes stores the credentials payload
    double-encoded (the entire JSON object is wrapped in quotes with
    backslash-escaped interior quotes). Historically we always attempted
    the unescape as a fallback which could accidentally parse an already
    clean blob. Only unwrap when the payload looks wrapped."""

    try:
        json.loads(creds_json)
    except json.JSONDecodeError:
        looks_escaped = creds_json.lstrip().startswith('"') or '\\"' in creds_json
        if looks_escaped:
            return json.loads(f'"{creds_json}"')
        raise
    return creds_json


@contextlib.contextmanager
def setup_gcp_credentials() -> Iterator[None]:
    """
    Set up GCP credentials from environment variable.

    Modal secrets are injected as environment variables. The GCP library
    expects GOOGLE_APPLICATION_CREDENTIALS to point to a file path. If
    credentials JSON is provided, write it to a temp file that's deleted
    on exit. This runs as a context manager to guarantee cleanup even if
    the caller raises mid-simulation; the previous fire-and-forget
    ``tempfile.mkstemp`` path leaked credential material on disk every
    time a container served a request.
    """
    # Log available GCP-related env vars for debugging
    gcp_vars = {
        k: v[:50] + "..." if len(v) > 50 else v
        for k, v in os.environ.items()
        if "GOOGLE" in k or "GCP" in k or "CREDENTIAL" in k
    }
    logger.info(f"GCP-related env vars: {list(gcp_vars.keys())}")

    # Check if credentials are already set as a file path
    if os.environ.get("GOOGLE_APPLICATION_CREDENTIALS"):
        logger.info("GOOGLE_APPLICATION_CREDENTIALS already set")
        yield
        return

    # Check for credentials JSON in various env var names
    creds_json = (
        os.environ.get("GOOGLE_APPLICATION_CREDENTIALS_JSON")
        or os.environ.get("GCP_CREDENTIALS_JSON")
        or os.environ.get("GOOGLE_CREDENTIALS")
        or os.environ.get("SERVICE_ACCOUNT_JSON")
    )

    if not creds_json:
        logger.warning("No GCP credentials found in environment variables")
        yield
        return

    normalized = _normalize_credentials_blob(creds_json)

    # ``NamedTemporaryFile(delete=True)`` removes the file when the context
    # exits (either normally or via exception). We restore any prior value
    # of ``GOOGLE_APPLICATION_CREDENTIALS`` so a retry in the same
    # container doesn't silently pick up a path that no longer exists.
    previous = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".json", delete=True
    ) as creds_file:
        creds_file.write(normalized)
        creds_file.flush()
        os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = creds_file.name
        logger.info(f"GCP credentials written to {creds_file.name}")
        try:
            yield
        finally:
            if previous is None:
                os.environ.pop("GOOGLE_APPLICATION_CREDENTIALS", None)
            else:
                os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = previous


def run_simulation_impl(params: dict) -> dict:
    """
    Execute economic simulation.

    Pure implementation with no Modal dependencies.
    Accepts SimulationOptions as a dict and returns EconomyComparison as a dict.
    """
    # Set up GCP credentials if needed. The credentials temp file is
    # cleaned up on exit so we never leave signed JSON material on disk.
    with setup_gcp_credentials():
        return _run_simulation_impl_core(params)


def _parse_year(params: dict[str, Any]) -> int:
    value = params.get("time_period") or params.get("year") or DEFAULT_YEAR
    return int(value)


def _normalise_period_key(period_key: Any) -> str:
    """Convert legacy ``start.stop`` period keys to v4 effective dates."""
    text = str(period_key)
    parts = text.split(".")
    if len(parts) > 1 and len(parts[0]) == 10:
        return parts[0]
    return text


def _normalise_reform(reform: dict[str, Any] | None) -> dict[str, Any] | None:
    if not reform:
        return None
    normalised: dict[str, Any] = {}
    for parameter, value in reform.items():
        if isinstance(value, dict):
            normalised[parameter] = {
                _normalise_period_key(period): period_value
                for period, period_value in value.items()
            }
        else:
            normalised[parameter] = value
    return normalised


def _resolve_dataset_name(
    country: str, requested_data: str | None, subsample: int | None
) -> str:
    if requested_data is None:
        return "enhanced_cps_2024" if country == "us" else "enhanced_frs_2023_24"

    requested = requested_data.split("@", maxsplit=1)[0]
    return DATASET_ALIASES.get(country, {}).get(requested, requested_data)


def _microframe_like(frame, weights: str):
    from microdf import MicroDataFrame

    return MicroDataFrame(frame.copy(), weights=weights)


def _person_group_column(person, entity: str) -> str:
    prefixed = f"person_{entity}_id"
    if prefixed in person.columns:
        return prefixed
    return f"{entity}_id"


def _subsample_us_dataset(dataset, subsample: int | None):
    if not subsample:
        return dataset

    from policyengine.tax_benefit_models.us.datasets import (
        PolicyEngineUSDataset,
        USYearData,
    )

    dataset.load()
    data = dataset.data
    household = data.household.head(int(subsample)).copy()
    household_ids = set(household["household_id"])

    person_household_col = _person_group_column(data.person, "household")
    person = data.person[data.person[person_household_col].isin(household_ids)].copy()

    def group_subset(entity: str):
        person_col = _person_group_column(person, entity)
        entity_id_col = f"{entity}_id"
        ids = set(person[person_col])
        frame = getattr(data, entity)
        return frame[frame[entity_id_col].isin(ids)].copy()

    subset_data = USYearData(
        person=_microframe_like(person, "person_weight"),
        marital_unit=_microframe_like(
            group_subset("marital_unit"), "marital_unit_weight"
        ),
        family=_microframe_like(group_subset("family"), "family_weight"),
        spm_unit=_microframe_like(group_subset("spm_unit"), "spm_unit_weight"),
        tax_unit=_microframe_like(group_subset("tax_unit"), "tax_unit_weight"),
        household=_microframe_like(household, "household_weight"),
    )
    subset_path = os.path.join(
        os.environ.get("POLICYENGINE_DATA_FOLDER", "/tmp/policyengine-data"),
        f"{dataset.id}_subsample_{subsample}.h5",
    )
    return PolicyEngineUSDataset(
        id=f"{dataset.id}_subsample_{subsample}",
        name=f"{dataset.name} subsample {subsample}",
        description=dataset.description,
        filepath=subset_path,
        year=dataset.year,
        is_output_dataset=dataset.is_output_dataset,
        data=subset_data,
    )


def _country_module(country: str):
    country = country.lower()
    if country == "us":
        return importlib.import_module("policyengine.tax_benefit_models.us")
    if country == "uk":
        return importlib.import_module("policyengine.tax_benefit_models.uk")
    raise ValueError(f"Unsupported country: {country}")


def _package_version(package_name: str) -> str | None:
    try:
        return version(package_name)
    except PackageNotFoundError:
        return None


def _load_dataset(params: dict[str, Any]):
    country = params.get("country", "us").lower()
    year = _parse_year(params)
    country_module = _country_module(country)
    dataset_name = _resolve_dataset_name(
        country, params.get("data"), params.get("subsample")
    )
    datasets = country_module.ensure_datasets(
        datasets=[dataset_name],
        years=[year],
        data_folder=os.environ.get(
            "POLICYENGINE_DATA_FOLDER", "/tmp/policyengine-data"
        ),
    )
    dataset = next(iter(datasets.values()))
    if country == "us":
        return _subsample_us_dataset(dataset, params.get("subsample"))
    return dataset


def _build_simulation(params: dict[str, Any], policy: dict[str, Any] | None):
    from policyengine.core import Simulation

    country = params.get("country", "us").lower()
    country_module = _country_module(country)
    dataset = _load_dataset(params)
    return Simulation(
        dataset=dataset,
        tax_benefit_model_version=country_module.model,
        policy=policy,
    )


def _change_sum(baseline, reform, variable: str, entity: str | None = None) -> float:
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


def _aggregate_sum(simulation, variable: str, entity: str | None = None) -> float:
    from policyengine.outputs import Aggregate, AggregateType

    output = Aggregate(
        simulation=simulation,
        variable=variable,
        entity=entity,
        aggregate_type=AggregateType.SUM,
    )
    output.run()
    return float(output.result)


def _aggregate_count(simulation, variable: str, entity: str | None = None) -> float:
    from policyengine.outputs import Aggregate, AggregateType

    output = Aggregate(
        simulation=simulation,
        variable=variable,
        entity=entity,
        aggregate_type=AggregateType.COUNT,
    )
    output.run()
    return float(output.result)


def _try_change_sum(
    baseline, reform, variable: str, entity: str | None = None
) -> float:
    try:
        return _change_sum(baseline, reform, variable, entity)
    except Exception:
        logger.warning("Unable to calculate change for %s", variable, exc_info=True)
        return 0.0


def _try_aggregate_sum(simulation, variable: str, entity: str | None = None) -> float:
    try:
        return _aggregate_sum(simulation, variable, entity)
    except Exception:
        logger.warning("Unable to calculate sum for %s", variable, exc_info=True)
        return 0.0


def _try_aggregate_count(simulation, variable: str, entity: str | None = None) -> float:
    try:
        return _aggregate_count(simulation, variable, entity)
    except Exception:
        logger.warning("Unable to calculate count for %s", variable, exc_info=True)
        return 0.0


def _budget_result(country: str, baseline, reform) -> dict[str, float]:
    tax_revenue_impact = _try_change_sum(
        baseline, reform, "household_tax", entity="household"
    )
    benefit_spending_impact = _try_change_sum(
        baseline, reform, "household_benefits", entity="household"
    )
    budgetary_impact = tax_revenue_impact - benefit_spending_impact
    result = {
        "tax_revenue_impact": tax_revenue_impact,
        "state_tax_revenue_impact": 0.0,
        "benefit_spending_impact": benefit_spending_impact,
        "budgetary_impact": budgetary_impact,
        "baseline_net_income": _try_aggregate_sum(
            baseline,
            "household_net_income",
            entity="household",
        ),
        "households": _try_aggregate_count(
            baseline,
            "household_net_income",
            entity="household",
        ),
    }
    if country == "us":
        result["state_tax_revenue_impact"] = _try_change_sum(
            baseline,
            reform,
            "household_state_income_tax",
            entity="tax_unit",
        )
    return result


def _rows(collection) -> list[dict[str, Any]]:
    return collection.dataframe.to_dict("records")


def _number_or_zero(value: Any) -> float:
    return float(value) if isinstance(value, int | float) else 0.0


def _empty_metric_pair() -> dict[str, float]:
    return {"baseline": 0.0, "reform": 0.0}


def _empty_labor_supply_response() -> dict[str, Any]:
    return {
        "decile": {
            "average": {"income": {}, "substitution": {}},
            "relative": {"income": {}, "substitution": {}},
        },
        "hours": {
            "baseline": 0.0,
            "reform": 0.0,
            "change": 0.0,
            "income_effect": 0.0,
            "substitution_effect": 0.0,
        },
        "income_lsr": 0.0,
        "substitution_lsr": 0.0,
        "relative_lsr": {"income": 0.0, "substitution": 0.0},
        "total_change": 0.0,
        "revenue_change": 0.0,
    }


def _decile_result(decile_rows: list[dict[str, Any]]) -> dict[str, dict[str, float]]:
    average: dict[str, float] = {}
    relative: dict[str, float] = {}
    for row in sorted(decile_rows, key=lambda item: item["decile"]):
        decile = str(row["decile"])
        average[decile] = _number_or_zero(row.get("absolute_change"))
        relative[decile] = _number_or_zero(row.get("relative_change"))
    return {"average": average, "relative": relative}


def _detailed_budget_result(
    program_rows: list[dict[str, Any]],
) -> dict[str, dict[str, float]]:
    return {
        row["program_name"]: {
            "baseline": _number_or_zero(row.get("baseline_total")),
            "reform": _number_or_zero(row.get("reform_total")),
            "difference": _number_or_zero(row.get("change")),
        }
        for row in program_rows
    }


def _inequality_result(analysis) -> dict[str, dict[str, float]]:
    return {
        "gini": {
            "baseline": _number_or_zero(analysis.baseline_inequality.gini),
            "reform": _number_or_zero(analysis.reform_inequality.gini),
        },
        "top_10_pct_share": {
            "baseline": _number_or_zero(analysis.baseline_inequality.top_10_share),
            "reform": _number_or_zero(analysis.reform_inequality.top_10_share),
        },
        "top_1_pct_share": {
            "baseline": _number_or_zero(analysis.baseline_inequality.top_1_share),
            "reform": _number_or_zero(analysis.reform_inequality.top_1_share),
        },
    }


def _poverty_rate(
    country: str,
    simulation,
    poverty_type: str,
    filters: dict[str, Any],
) -> float:
    from policyengine.outputs.poverty import Poverty

    variable = POVERTY_VARIABLES[country][poverty_type]
    if variable is None:
        return 0.0

    poverty = Poverty(
        simulation=simulation,
        poverty_variable=variable,
        poverty_type=poverty_type,
        entity="person",
        **filters,
    )
    poverty.run()
    return _number_or_zero(poverty.rate)


def _try_poverty_pair(
    country: str,
    baseline,
    reform,
    poverty_type: str,
    filters: dict[str, Any],
) -> dict[str, float]:
    try:
        return {
            "baseline": _poverty_rate(country, baseline, poverty_type, filters),
            "reform": _poverty_rate(country, reform, poverty_type, filters),
        }
    except Exception:
        logger.warning(
            "Unable to calculate %s poverty for filters %s",
            poverty_type,
            filters,
            exc_info=True,
        )
        return _empty_metric_pair()


def _poverty_result(country: str, baseline, reform) -> dict[str, Any]:
    return {
        poverty_type: {
            group: _try_poverty_pair(country, baseline, reform, poverty_type, filters)
            for group, filters in AGE_GROUPS.items()
        }
        for poverty_type in POVERTY_TYPES
    }


def _poverty_by_gender_result(country: str, baseline, reform) -> dict[str, Any]:
    return {
        poverty_type: {
            group: _try_poverty_pair(country, baseline, reform, poverty_type, filters)
            for group, filters in GENDER_GROUPS.items()
        }
        for poverty_type in POVERTY_TYPES
    }


def _poverty_by_race_result(country: str, baseline, reform) -> dict[str, Any] | None:
    if country != "us":
        return None
    return {
        "poverty": {
            group: _try_poverty_pair(country, baseline, reform, "poverty", filters)
            for group, filters in RACE_GROUPS.items()
        }
    }


def _intra_decile_rows(country: str, baseline, reform) -> list[dict[str, Any]]:
    from policyengine.outputs import compute_intra_decile_impacts

    income_variable = (
        "household_net_income"
        if country == "us"
        else "equiv_hbai_household_net_income"
    )
    return _rows(
        compute_intra_decile_impacts(
            baseline_simulation=baseline,
            reform_simulation=reform,
            income_variable=income_variable,
        )
    )


def _try_intra_decile_rows(country: str, baseline, reform) -> list[dict[str, Any]]:
    try:
        return _intra_decile_rows(country, baseline, reform)
    except Exception:
        logger.warning("Unable to calculate intra-decile impact", exc_info=True)
        return []


def _intra_decile_result(rows: list[dict[str, Any]]) -> dict[str, Any]:
    output = {
        "all": {label: 0.0 for label in INTRA_DECILE_FIELDS},
        "deciles": {label: [] for label in INTRA_DECILE_FIELDS},
    }
    sorted_rows = sorted(rows, key=lambda row: row["decile"])

    for label, field in INTRA_DECILE_FIELDS.items():
        decile_values = [
            _number_or_zero(row.get(field))
            for row in sorted_rows
            if row.get("decile") != 0
        ]
        output["deciles"][label] = decile_values

        overall = next((row for row in sorted_rows if row.get("decile") == 0), None)
        if overall is not None:
            output["all"][label] = _number_or_zero(overall.get(field))
        elif decile_values:
            output["all"][label] = sum(decile_values) / len(decile_values)

    return output


def _congressional_district_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    for row in rows:
        state_fips = int(_number_or_zero(row.get("state_fips")))
        district_number = int(_number_or_zero(row.get("district_number")))
        output.append(
            {
                "district": f"{state_fips:02d}-{district_number:02d}",
                "average_household_income_change": _number_or_zero(
                    row.get("average_household_income_change")
                ),
                "relative_household_income_change": _number_or_zero(
                    row.get("relative_household_income_change")
                ),
                "winner_percentage": _number_or_zero(row.get("winner_percentage")),
                "loser_percentage": _number_or_zero(row.get("loser_percentage")),
                "no_change_percentage": _number_or_zero(
                    row.get("no_change_percentage")
                ),
            }
        )
    return output


def _congressional_district_impact(
    country: str, baseline, reform
) -> dict[str, Any] | None:
    if country != "us":
        return None
    try:
        from policyengine.outputs import compute_us_congressional_district_impacts

        impact = compute_us_congressional_district_impacts(
            baseline_simulation=baseline,
            reform_simulation=reform,
        )
    except Exception:
        logger.warning("Unable to calculate congressional district impact", exc_info=True)
        return None

    return {"districts": _congressional_district_rows(impact.district_results or [])}


def _legacy_macro_result(
    *,
    country: str,
    params: dict[str, Any],
    baseline,
    reform,
    analysis,
    budget: dict[str, float],
    metadata: dict[str, Any],
) -> dict[str, Any]:
    decile_rows = _rows(analysis.decile_impacts)
    program_rows = _rows(analysis.program_statistics)
    intra_decile_rows = _try_intra_decile_rows(country, baseline, reform)
    country_package = f"policyengine-{country}"

    return {
        "budget": budget,
        "detailed_budget": _detailed_budget_result(program_rows),
        "decile": _decile_result(decile_rows),
        "inequality": _inequality_result(analysis),
        "poverty": _poverty_result(country, baseline, reform),
        "poverty_by_gender": _poverty_by_gender_result(country, baseline, reform),
        "poverty_by_race": _poverty_by_race_result(country, baseline, reform),
        "intra_decile": _intra_decile_result(intra_decile_rows),
        "wealth_decile": None,
        "intra_wealth_decile": None,
        "labor_supply_response": _empty_labor_supply_response(),
        "constituency_impact": None,
        "local_authority_impact": None,
        "congressional_district_impact": _congressional_district_impact(
            country,
            baseline,
            reform,
        ),
        "cliff_impact": None,
        "model_version": _package_version(country_package),
        "policyengine_version": _package_version("policyengine"),
        "data_version": params.get("data_version"),
        "dataset": metadata.get("dataset"),
        "metadata": metadata,
        # Preserve the row-oriented PolicyEngine 4.4.x outputs as extra fields.
        "decile_impacts": decile_rows,
        "program_statistics": program_rows,
        "intra_decile_rows": intra_decile_rows,
    }


def _run_simulation_impl_core(params: dict) -> dict:
    simulation_params, telemetry, metadata = split_internal_payload(params)

    logger.info(
        "Starting simulation for country=%s run_id=%s process_id=%s",
        simulation_params.get("country", "unknown"),
        getattr(telemetry, "run_id", None),
        getattr(telemetry, "process_id", None),
    )
    if metadata:
        logger.info("Received simulation metadata keys: %s", sorted(metadata))

    country = simulation_params.get("country", "us").lower()
    baseline_policy = _normalise_reform(simulation_params.get("baseline"))
    reform_policy = _normalise_reform(simulation_params.get("reform"))

    logger.info("Initialising baseline and reform simulations")
    baseline = _build_simulation(simulation_params, baseline_policy)
    reform = _build_simulation(simulation_params, reform_policy)

    logger.info("Calculating economic impact")
    country_module = _country_module(country)
    analysis = country_module.economic_impact_analysis(baseline, reform)
    metadata = {
        "country": country,
        "year": _parse_year(simulation_params),
        "dataset": getattr(baseline.dataset, "filepath", None),
    }
    result = _legacy_macro_result(
        country=country,
        params=simulation_params,
        baseline=baseline,
        reform=reform,
        analysis=analysis,
        budget=_budget_result(country, baseline, reform),
        metadata=metadata,
    )
    logger.info("Comparison complete")
    return result
