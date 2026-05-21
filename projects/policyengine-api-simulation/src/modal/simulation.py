"""
Simulation implementation - pure logic with snapshotted imports.

This module avoids importing policyengine at module level so the worker can
load the requested country module without triggering cross-country imports.
No Modal dependencies here.
"""

import contextlib
import json
import logging
import os
import tempfile
from importlib import import_module
from typing import Any, Iterator

from src.modal.simulation_output_adapter import adapt_analysis_to_legacy_macro_output
from src.modal.telemetry import split_internal_payload

logger = logging.getLogger(__name__)

os.environ.setdefault("POLICYENGINE_SKIP_COUNTRY_IMPORTS", "1")

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
        "hf://policyengine/policyengine-uk-data-private/enhanced_frs_2023_24.h5": "enhanced_frs_2023_24",
        "frs": "frs_2023_24",
        "frs_2023_24": "frs_2023_24",
        "hf://policyengine/policyengine-uk-data-private/frs_2023_24.h5": "frs_2023_24",
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
    Accepts the gateway simulation payload and returns the legacy macro result dict.
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


def _normalise_policy(policy: dict[str, Any] | None) -> dict[str, Any] | None:
    if not policy:
        return None

    normalised: dict[str, Any] = {}
    for parameter, value in policy.items():
        if isinstance(value, dict):
            normalised[parameter] = {
                _normalise_period_key(period): period_value
                for period, period_value in value.items()
            }
        else:
            normalised[parameter] = value
    return normalised


def _resolve_dataset_name(country: str, requested_data: str | None) -> str:
    if requested_data is None:
        return "enhanced_cps_2024" if country == "us" else "enhanced_frs_2023_24"

    requested_without_revision = requested_data.split("@", maxsplit=1)[0]
    return DATASET_ALIASES.get(country, {}).get(
        requested_without_revision, requested_data
    )


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
        metadata=getattr(dataset, "metadata", {}),
        metadata_filepath=getattr(dataset, "metadata_filepath", None),
        data=subset_data,
    )


def _country_module(country: str):
    country = country.lower()
    if country not in {"us", "uk"}:
        raise ValueError(f"Unsupported country: {country}")

    return import_module(f"policyengine.tax_benefit_models.{country}")


def _load_dataset(params: dict[str, Any]):
    country = params.get("country", "us").lower()
    year = _parse_year(params)
    country_module = _country_module(country)
    dataset_name = _resolve_dataset_name(country, params.get("data"))
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


def _build_simulation(
    params: dict[str, Any],
    *,
    dataset,
    policy: dict[str, Any] | None,
):
    from policyengine.core import Simulation

    country_module = _country_module(params.get("country", "us"))
    return Simulation(
        dataset=dataset,
        tax_benefit_model_version=country_module.model,
        policy=policy,
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


def _budget_result(country: str, baseline, reform) -> dict[str, float]:
    tax_revenue_impact = _try_change_output_variable(
        baseline, reform, "household_tax", entity="household"
    )
    benefit_spending_impact = _try_change_output_variable(
        baseline, reform, "household_benefits", entity="household"
    )
    state_tax_revenue_impact = (
        _try_change_output_variable(
            baseline,
            reform,
            "household_state_income_tax",
            entity="household",
        )
        if country == "us"
        else 0.0
    )

    return {
        "tax_revenue_impact": tax_revenue_impact,
        "state_tax_revenue_impact": state_tax_revenue_impact,
        "benefit_spending_impact": benefit_spending_impact,
        "budgetary_impact": tax_revenue_impact - benefit_spending_impact,
        "households": _try_sum_output_variable(
            baseline, "household_weight", entity="household"
        ),
        "baseline_net_income": _try_sum_output_variable(
            baseline, "household_net_income", entity="household"
        ),
    }


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


def _additional_poverty_outputs(country: str, baseline, reform) -> dict[str, Any]:
    prefix = "us" if country == "us" else "uk"
    output = {
        "baseline_poverty_by_age": _try_compute_output(
            "baseline poverty by age",
            _poverty_module_function(f"calculate_{prefix}_poverty_by_age"),
            baseline,
        ),
        "reform_poverty_by_age": _try_compute_output(
            "reform poverty by age",
            _poverty_module_function(f"calculate_{prefix}_poverty_by_age"),
            reform,
        ),
        "baseline_poverty_by_gender": _try_compute_output(
            "baseline poverty by gender",
            _poverty_module_function(f"calculate_{prefix}_poverty_by_gender"),
            baseline,
        ),
        "reform_poverty_by_gender": _try_compute_output(
            "reform poverty by gender",
            _poverty_module_function(f"calculate_{prefix}_poverty_by_gender"),
            reform,
        ),
        "baseline_poverty_by_race": None,
        "reform_poverty_by_race": None,
    }
    if country == "us":
        output["baseline_poverty_by_race"] = _try_compute_output(
            "baseline poverty by race",
            _poverty_module_function("calculate_us_poverty_by_race"),
            baseline,
        )
        output["reform_poverty_by_race"] = _try_compute_output(
            "reform poverty by race",
            _poverty_module_function("calculate_us_poverty_by_race"),
            reform,
        )
    return output


def _intra_decile_output(baseline, reform):
    from policyengine.outputs.intra_decile_impact import compute_intra_decile_impacts

    return _try_compute_output(
        "intra-decile impacts",
        compute_intra_decile_impacts,
        baseline,
        reform,
        income_variable="household_net_income",
        entity="household",
    )


def _congressional_district_impact(country: str, baseline, reform):
    if country != "us":
        return None

    from policyengine.outputs.congressional_district_impact import (
        compute_us_congressional_district_impacts,
    )

    impact = _try_compute_output(
        "congressional district impacts",
        compute_us_congressional_district_impacts,
        baseline,
        reform,
    )
    return getattr(impact, "district_results", None) if impact is not None else None


def _uk_constituency_impact(country: str, baseline, reform):
    if country != "uk":
        return None

    impact = _try_compute_output(
        "constituency impacts",
        _output_module_function(
            "constituency_impact", "compute_uk_constituency_impacts"
        ),
        baseline,
        reform,
    )
    if impact is None:
        return None
    return getattr(impact, "constituency_results", None)


def _uk_local_authority_impact(country: str, baseline, reform):
    if country != "uk":
        return None

    impact = _try_compute_output(
        "local authority impacts",
        _output_module_function(
            "local_authority_impact", "compute_uk_local_authority_impacts"
        ),
        baseline,
        reform,
    )
    if impact is None:
        return None
    return getattr(impact, "local_authority_results", None)


def _model_version(country_module) -> str:
    return str(getattr(country_module.model, "version", ""))


def _data_version(params: dict[str, Any], dataset) -> str:
    if params.get("data_version"):
        return str(params["data_version"])
    metadata = getattr(dataset, "metadata", {}) or {}
    for key in ("data_version", "version"):
        value = metadata.get(key)
        if value is not None:
            return str(value)
    return ""


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
    country_module = _country_module(country)
    dataset = _load_dataset(simulation_params)
    baseline_policy = _normalise_policy(simulation_params.get("baseline"))
    reform_policy = _normalise_policy(simulation_params.get("reform"))

    logger.info("Initialising baseline and reform simulations")
    baseline = _build_simulation(
        simulation_params,
        dataset=dataset,
        policy=baseline_policy,
    )
    reform = _build_simulation(
        simulation_params,
        dataset=dataset,
        policy=reform_policy,
    )

    logger.info("Calculating economic impact")
    analysis = country_module.economic_impact_analysis(baseline, reform)
    budget = _budget_result(country, baseline, reform)
    poverty_outputs = _additional_poverty_outputs(country, baseline, reform)
    intra_decile = _intra_decile_output(baseline, reform)
    congressional_district_impact = _congressional_district_impact(
        country, baseline, reform
    )
    constituency_impact = _uk_constituency_impact(country, baseline, reform)
    local_authority_impact = _uk_local_authority_impact(country, baseline, reform)
    logger.info("Comparison complete")

    return adapt_analysis_to_legacy_macro_output(
        country=country,
        model_version=_model_version(country_module),
        data_version=_data_version(simulation_params, dataset),
        budget=budget,
        analysis=analysis,
        intra_decile=intra_decile,
        congressional_district_impact=congressional_district_impact,
        constituency_impact=constituency_impact,
        local_authority_impact=local_authority_impact,
        **poverty_outputs,
    )
