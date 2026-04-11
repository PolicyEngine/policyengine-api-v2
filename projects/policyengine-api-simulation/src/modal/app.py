"""
PolicyEngine Simulation - Versioned Modal App

This app contains the heavy simulation workload with snapshotted models.
Each deployment creates a versioned app (e.g., policyengine-simulation-us1-459-0-uk2-65-9).

The gateway app (policyengine-simulation-gateway) routes requests to these versioned apps.
"""

import modal
import os
from time import perf_counter

from src.modal._image_setup import snapshot_models
from src.modal.observability import (
    build_lifecycle_event,
    build_metric_attributes,
    build_span_attributes,
    QUEUE_DURATION_METRIC_NAME,
    FAILURE_COUNT_METRIC_NAME,
    duration_since_requested_at,
    get_observability,
    parse_bool,
)

# Get versions from environment or use defaults
US_VERSION = os.environ.get("POLICYENGINE_US_VERSION", "1.562.3")
UK_VERSION = os.environ.get("POLICYENGINE_UK_VERSION", "2.65.9")


def get_app_name(us_version: str, uk_version: str) -> str:
    """
    Generate versioned app name from package versions.

    Replaces dots with dashes for URL safety.
    Example: us1.459.0, uk2.65.9 -> policyengine-simulation-us1-459-0-uk2-65-9
    """
    us_safe = us_version.replace(".", "-")
    uk_safe = uk_version.replace(".", "-")
    return f"policyengine-simulation-us{us_safe}-uk{uk_safe}"


# App name can be overridden via environment variable, otherwise generated from versions
APP_NAME = os.environ.get("MODAL_APP_NAME", get_app_name(US_VERSION, UK_VERSION))

# App definition with versioned name
app = modal.App(APP_NAME)

# Secrets
# GCP credentials are shared across environments (always from main)
gcp_secret = modal.Secret.from_name("gcp-credentials", environment_name="main")
# Logfire secret is environment-specific
logfire_secret = modal.Secret.from_name("policyengine-logfire")

# Heavy image with model snapshot for simulation
simulation_image = (
    modal.Image.debian_slim(python_version="3.13")
    .pip_install(
        f"policyengine-us=={US_VERSION}",
        f"policyengine-uk=={UK_VERSION}",
        "policyengine==0.13.0",
        "tables>=3.10.2",
        "google-cloud-storage>=3.1.1",
        "logfire",
        "opentelemetry-sdk>=1.30.0,<2.0.0",
        "opentelemetry-exporter-otlp-proto-http>=1.30.0,<2.0.0",
    )
    .add_local_python_source("src.modal", copy=True)
    .add_local_python_source("policyengine_api_simulation", copy=True)
    .add_local_python_source("policyengine_fastapi", copy=True)
    .run_function(snapshot_models)
)


def configure_logfire(service_name: str = "policyengine-simulation"):
    """Configure Logfire for observability. Call at start of each function."""
    import logfire

    token = os.environ.get("LOGFIRE_TOKEN", "")
    if not token:
        return

    logfire.configure(
        service_name=service_name,
        token=token,
        environment=os.environ.get("LOGFIRE_ENVIRONMENT", "production"),
        console=False,
    )


def should_use_logfire() -> bool:
    token = os.environ.get("LOGFIRE_TOKEN", "")
    if not token:
        return False
    if parse_bool(os.environ.get("OBSERVABILITY_ENABLED"), False) and not parse_bool(
        os.environ.get("OBSERVABILITY_SHADOW_MODE"),
        True,
    ):
        return False
    return True


@app.function(
    image=simulation_image,
    cpu=8.0,
    memory=32768,
    timeout=3600,
    retries=0,
    max_containers=100,
    secrets=[gcp_secret, logfire_secret],
)
def run_simulation(params: dict) -> dict:
    """
    Execute economic simulation.

    Imports the snapshotted implementation at runtime.
    Logs input params and output result to Logfire for observability.
    """
    import logfire

    from src.modal.simulation import run_simulation_impl

    observability = get_observability("policyengine-simulation-worker")
    telemetry = dict(params.get("_telemetry") or {})
    telemetry.update(
        {
            "country": params.get("country"),
            "country_package_name": (
                "policyengine-us" if params.get("country") == "us" else "policyengine-uk"
            ),
            "country_package_version": (
                US_VERSION if params.get("country") == "us" else UK_VERSION
            ),
            "policyengine_version": "0.13.0",
            "modal_app_name": APP_NAME,
        }
    )
    configured_capture_mode = getattr(observability.config, "tracer_capture_mode", "disabled")
    if telemetry.get("capture_mode") in (None, "disabled") and configured_capture_mode != "disabled":
        telemetry["capture_mode"] = configured_capture_mode
    metric_attributes = build_metric_attributes(
        telemetry,
        service="policyengine-simulation-worker",
    )
    start = perf_counter()
    queue_duration = duration_since_requested_at(telemetry)
    if queue_duration is not None:
        observability.emit_histogram(
            QUEUE_DURATION_METRIC_NAME,
            queue_duration,
            attributes=build_metric_attributes(
                telemetry,
                service="policyengine-simulation-worker",
                stage="worker.started",
                status="running",
            ),
        )

    observability.emit_lifecycle_event(
        build_lifecycle_event(
            stage="worker.started",
            status="running",
            service="policyengine-simulation-worker",
            telemetry=telemetry,
            details={"queue_duration_seconds": queue_duration},
        )
    )

    use_logfire = should_use_logfire()
    if use_logfire:
        configure_logfire()

    try:
        with observability.span(
            "run_simulation",
            build_span_attributes(
                telemetry,
                service="policyengine-simulation-worker",
            ),
            parent_traceparent=telemetry.get("traceparent"),
        ) as otel_span:
            otel_span.set_attribute("run_id", telemetry.get("run_id"))
            if queue_duration is not None:
                otel_span.set_attribute(
                    "queue_duration_seconds",
                    queue_duration,
                )
            current_traceparent = otel_span.get_traceparent()
            if current_traceparent:
                telemetry["traceparent"] = current_traceparent
            if use_logfire:
                with logfire.span(
                    "run_simulation",
                    input_params=params,
                ) as span:
                    result = run_simulation_impl(params, observability, telemetry)
                    span.set_attribute("output_result", result)
            else:
                result = run_simulation_impl(params, observability, telemetry)

            duration = perf_counter() - start
            observability.emit_counter(
                "policyengine.simulation.run.count",
                attributes={**metric_attributes, "status": "complete"},
            )
            observability.emit_histogram(
                "policyengine.simulation.run.duration.seconds",
                duration,
                attributes={**metric_attributes, "status": "complete"},
            )
            observability.emit_lifecycle_event(
                build_lifecycle_event(
                    stage="worker.completed",
                    status="complete",
                    service="policyengine-simulation-worker",
                    telemetry=telemetry,
                    duration_seconds=duration,
                )
            )
            return result
    except Exception as exc:
        duration = perf_counter() - start
        observability.emit_counter(
            FAILURE_COUNT_METRIC_NAME,
            attributes={
                **metric_attributes,
                "stage": "result.failed",
                "status": "failed",
            },
        )
        observability.emit_lifecycle_event(
            build_lifecycle_event(
                stage="result.failed",
                status="failed",
                service="policyengine-simulation-worker",
                telemetry=telemetry,
                duration_seconds=duration,
                details={"error": str(exc)},
            )
        )
        raise
    finally:
        observability.flush()
        if use_logfire:
            logfire.force_flush()
