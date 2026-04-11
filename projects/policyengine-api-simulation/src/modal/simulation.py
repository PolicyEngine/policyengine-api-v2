"""
Simulation implementation - pure logic with snapshotted imports.

This module has policyengine imports at module level so they are
captured in Modal's image snapshot. No Modal dependencies here.
"""

import json
import logging
import os
import tempfile
from time import perf_counter
from typing import Any

# Module-level imports - these are SNAPSHOTTED at image build time
from policyengine.simulation import Simulation, SimulationOptions

from src.modal.artifact_store import build_artifact_store
from src.modal.observability import observe_stage
from src.modal.telemetry import split_internal_payload
from src.modal.tracer_capture import (
    export_tracer_diagnostics,
    resolve_capture_mode,
    should_trace_simulation,
)

logger = logging.getLogger(__name__)


def setup_gcp_credentials():
    """
    Set up GCP credentials from environment variable.

    Modal secrets are injected as environment variables. The GCP library
    expects GOOGLE_APPLICATION_CREDENTIALS to point to a file path.
    If credentials JSON is provided, write it to a temp file.
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
        return

    # Check for credentials JSON in various env var names
    creds_json = (
        os.environ.get("GOOGLE_APPLICATION_CREDENTIALS_JSON")
        or os.environ.get("GCP_CREDENTIALS_JSON")
        or os.environ.get("GOOGLE_CREDENTIALS")
        or os.environ.get("SERVICE_ACCOUNT_JSON")
    )

    if creds_json:
        # Write credentials to a temp file
        fd, path = tempfile.mkstemp(suffix=".json")
        with os.fdopen(fd, "w") as f:
            # Handle both raw JSON and escaped JSON strings
            try:
                json.loads(creds_json)  # Validate it's valid JSON
                f.write(creds_json)
            except json.JSONDecodeError:
                # Try unescaping if it's a string-encoded JSON
                f.write(json.loads(f'"{creds_json}"'))

        os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = path
        logger.info(f"GCP credentials written to {path}")
    else:
        logger.warning("No GCP credentials found in environment variables")


def run_simulation_impl(
    params: dict,
    observability: Any = None,
    telemetry_context: dict[str, Any] | None = None,
) -> dict:
    """
    Execute economic simulation.

    Pure implementation with no Modal dependencies.
    Accepts SimulationOptions as a dict and returns EconomyComparison as a dict.
    """
    start = perf_counter()
    simulation_params, telemetry, metadata = split_internal_payload(params)
    event_telemetry = dict(
        telemetry.model_dump(mode="json")
        if telemetry is not None
        else (telemetry_context or {})
    )
    observability_config = None if observability is None else getattr(
        observability, "config", None
    )
    capture_mode = resolve_capture_mode(
        None if telemetry is None else telemetry.capture_mode,
        None
        if observability_config is None
        else observability_config.tracer_capture_mode,
    )
    if capture_mode:
        event_telemetry["capture_mode"] = capture_mode
    trace_enabled = should_trace_simulation(capture_mode)
    artifact_store = build_artifact_store(
        None if observability_config is None else observability_config.artifact_bucket,
        prefix=(
            "simulation-observability"
            if observability_config is None
            else observability_config.artifact_prefix
        ),
    )
    simulation = None
    failed = False

    if observability is not None:
        with observe_stage(
            observability,
            stage="worker.credentials.ready",
            service="policyengine-simulation-worker",
            telemetry=event_telemetry,
            record_failure_counter=True,
        ):
            setup_gcp_credentials()
    else:
        setup_gcp_credentials()

    logger.info(
        "Starting simulation for country=%s run_id=%s process_id=%s",
        simulation_params.get("country", "unknown"),
        getattr(telemetry, "run_id", None),
        getattr(telemetry, "process_id", None),
    )
    if metadata:
        logger.info("Received simulation metadata keys: %s", sorted(metadata))

    # Validate and create simulation options
    if observability is not None:
        with observe_stage(
            observability,
            stage="worker.options.validated",
            service="policyengine-simulation-worker",
            telemetry=event_telemetry,
            record_failure_counter=True,
        ):
            options = SimulationOptions.model_validate(simulation_params)
    else:
        options = SimulationOptions.model_validate(simulation_params)
    logger.info("Initialising simulation from input")

    # Create simulation instance
    simulation_kwargs = options.model_dump()
    if trace_enabled:
        simulation_kwargs["trace"] = True
    if observability is not None:
        with observe_stage(
            observability,
            stage="worker.simulation.constructed",
            service="policyengine-simulation-worker",
            telemetry=event_telemetry,
            record_failure_counter=True,
        ):
            simulation = Simulation(**simulation_kwargs)
    else:
        simulation = Simulation(**simulation_kwargs)
    logger.info("Calculating comparison")

    try:
        # Run the economy comparison calculation
        if observability is not None:
            with observe_stage(
                observability,
                stage="worker.comparison.calculated",
                service="policyengine-simulation-worker",
                telemetry=event_telemetry,
                record_failure_counter=True,
            ):
                result = simulation.calculate_economy_comparison()
        else:
            result = simulation.calculate_economy_comparison()
        logger.info("Comparison complete")

        # Use mode='json' to ensure numpy arrays are converted to lists
        if observability is not None:
            with observe_stage(
                observability,
                stage="worker.result.serialized",
                service="policyengine-simulation-worker",
                telemetry=event_telemetry,
                record_failure_counter=True,
            ):
                serialized = result.model_dump(mode="json")
        else:
            serialized = result.model_dump(mode="json")
        return serialized
    except Exception:
        failed = True
        raise
    finally:
        if observability is not None and simulation is not None and trace_enabled:
            try:
                with observe_stage(
                    observability,
                    stage="worker.tracer.exported",
                    service="policyengine-simulation-worker",
                    telemetry=event_telemetry,
                    record_failure_counter=True,
                    details={"capture_mode": capture_mode},
                ) as stage_observation:
                    _, tracer_details = export_tracer_diagnostics(
                        simulation=simulation,
                        observability=observability,
                        telemetry=event_telemetry,
                        service="policyengine-simulation-worker",
                        capture_mode=capture_mode,
                        run_duration_seconds=perf_counter() - start,
                        failed=failed,
                        artifact_store=artifact_store,
                        slow_run_threshold_seconds=(
                            30.0
                            if observability_config is None
                            else observability_config.slow_run_threshold_seconds
                        ),
                        success_sample_rate=(
                            0.0
                            if observability_config is None
                            else observability_config.tracer_success_sample_rate
                        ),
                        include_computation_log=(
                            False
                            if observability_config is None
                            else observability_config.tracer_include_computation_log
                        ),
                    )
                    stage_observation.details.update(tracer_details)
            except Exception:
                logger.exception(
                    "Tracer export failed for run_id=%s",
                    None if telemetry is None else telemetry.run_id,
                )
