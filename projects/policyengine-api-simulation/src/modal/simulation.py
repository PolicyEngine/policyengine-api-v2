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
from typing import Iterator

# Module-level imports - these are SNAPSHOTTED at image build time
from policyengine.simulation import Simulation, SimulationOptions

from src.modal.telemetry import split_internal_payload

logger = logging.getLogger(__name__)


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

    # Validate and create simulation options
    options = SimulationOptions.model_validate(simulation_params)
    logger.info("Initialising simulation from input")

    # Create simulation instance
    simulation = Simulation(**options.model_dump())
    logger.info("Calculating comparison")

    # Run the economy comparison calculation
    result = simulation.calculate_economy_comparison()
    logger.info("Comparison complete")

    # Use mode='json' to ensure numpy arrays are converted to lists
    return result.model_dump(mode="json")
