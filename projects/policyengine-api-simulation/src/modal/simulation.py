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

from src.modal.release_bundle import resolve_bundle_dataset_name
from src.modal.simulation_macro_output_builder import SimulationMacroOutputBuilder
from src.modal.telemetry import split_internal_payload

logger = logging.getLogger(__name__)

os.environ.setdefault("POLICYENGINE_SKIP_COUNTRY_IMPORTS", "1")

DEFAULT_YEAR = 2026


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
    return resolve_bundle_dataset_name(country, requested_data)


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
    output = SimulationMacroOutputBuilder(
        country=country,
        simulation_params=simulation_params,
        country_module=country_module,
        dataset=dataset,
        baseline=baseline,
        reform=reform,
        analysis=analysis,
    ).serialize()
    logger.info("Comparison complete")
    return output
