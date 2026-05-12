"""
Simulation implementation - pure logic with snapshotted imports.

This module has policyengine imports at module level so they are
captured in Modal's image snapshot. No Modal dependencies here.
"""

import contextlib
import json
import logging
import os
import tempfile
from typing import Any, Iterator

try:
    from src.modal.telemetry import split_internal_payload
except ModuleNotFoundError:
    from modal.telemetry import split_internal_payload

logger = logging.getLogger(__name__)


DEFAULT_YEAR = 2026
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
    import policyengine as pe

    country = country.lower()
    if country == "us":
        return pe.us
    if country == "uk":
        return pe.uk
    raise ValueError(f"Unsupported country: {country}")


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


def _try_change_sum(
    baseline, reform, variable: str, entity: str | None = None
) -> float:
    try:
        return _change_sum(baseline, reform, variable, entity)
    except Exception:
        logger.warning("Unable to calculate change for %s", variable, exc_info=True)
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
        "benefit_spending_impact": benefit_spending_impact,
        "budgetary_impact": budgetary_impact,
    }
    if country == "us":
        result["state_tax_revenue_impact"] = _try_change_sum(
            baseline,
            reform,
            "household_state_income_tax",
            entity="tax_unit",
        )
    return result


def _poverty_result(country: str, baseline, reform) -> dict[str, list[dict[str, Any]]]:
    import policyengine as pe

    if country == "us":
        baseline_poverty = pe.us.economic_impact_analysis(
            baseline, reform
        ).baseline_poverty
        reform_poverty = pe.us.economic_impact_analysis(baseline, reform).reform_poverty
    else:
        baseline_poverty = pe.uk.economic_impact_analysis(
            baseline, reform
        ).baseline_poverty
        reform_poverty = pe.uk.economic_impact_analysis(baseline, reform).reform_poverty

    return {
        "baseline": baseline_poverty.dataframe.to_dict("records"),
        "reform": reform_poverty.dataframe.to_dict("records"),
    }


def _analysis_result(country: str, baseline, reform) -> dict[str, Any]:
    import policyengine as pe

    if country == "us":
        analysis = pe.us.economic_impact_analysis(baseline, reform)
    else:
        analysis = pe.uk.economic_impact_analysis(baseline, reform)

    return {
        "decile_impacts": analysis.decile_impacts.dataframe.to_dict("records"),
        "program_statistics": analysis.program_statistics.dataframe.to_dict("records"),
        "poverty": {
            "baseline": analysis.baseline_poverty.dataframe.to_dict("records"),
            "reform": analysis.reform_poverty.dataframe.to_dict("records"),
        },
        "inequality": {
            "baseline": _inequality_summary(analysis.baseline_inequality),
            "reform": _inequality_summary(analysis.reform_inequality),
        },
    }


def _inequality_summary(inequality) -> dict[str, Any]:
    return {
        "income_variable": inequality.income_variable,
        "entity": inequality.entity,
        "gini": inequality.gini,
        "top_10_share": inequality.top_10_share,
        "top_1_share": inequality.top_1_share,
        "bottom_50_share": inequality.bottom_50_share,
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
    analysis = _analysis_result(country, baseline, reform)
    analysis["budget"] = _budget_result(country, baseline, reform)
    analysis["metadata"] = {
        "country": country,
        "year": _parse_year(simulation_params),
        "dataset": getattr(baseline.dataset, "filepath", None),
    }
    logger.info("Comparison complete")
    return analysis
