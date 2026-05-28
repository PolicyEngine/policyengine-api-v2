"""
PolicyEngine Simulation - Versioned Modal App

This app contains the heavy simulation workload with snapshotted models.
Each deployment creates a versioned app (e.g., policyengine-simulation-py4-10-0).

The gateway app (policyengine-simulation-gateway) routes requests to these versioned apps.
"""

import modal
import os

from src.modal._image_setup import snapshot_models
from src.modal.dependency_pins import project_dependency_pin
from src.modal.logging_redaction import redact_params_for_logging
from policyengine_api_simulation.release_bundle import get_bundled_country_model_version

POLICYENGINE_VERSION = os.environ.get("POLICYENGINE_VERSION") or project_dependency_pin(
    "policyengine"
)
POLICYENGINE_CORE_VERSION = os.environ.get(
    "POLICYENGINE_CORE_VERSION"
) or project_dependency_pin("policyengine-core")

# Get versions from environment or the bundled policyengine.py release manifest.
US_VERSION = os.environ.get(
    "POLICYENGINE_US_VERSION"
) or get_bundled_country_model_version("us")
UK_VERSION = os.environ.get(
    "POLICYENGINE_UK_VERSION"
) or get_bundled_country_model_version("uk")


def get_app_name(policyengine_version: str) -> str:
    """
    Generate versioned app name from the policyengine.py package version.

    Replaces dots with dashes for URL safety.
    Example: 4.10.0 -> policyengine-simulation-py4-10-0
    """
    policyengine_safe = policyengine_version.replace(".", "-")
    return f"policyengine-simulation-py{policyengine_safe}"


# App name can be overridden via environment variable, otherwise generated from versions
APP_NAME = os.environ.get("MODAL_APP_NAME", get_app_name(POLICYENGINE_VERSION))

# App definition with versioned name
app = modal.App(APP_NAME)

# Secrets
# GCP credentials are shared across environments (always from main)
gcp_secret = modal.Secret.from_name("gcp-credentials", environment_name="main")
data_secret = modal.Secret.from_name("policyengine-data-credentials")
# Logfire secret is environment-specific
logfire_secret = modal.Secret.from_name("policyengine-logfire")

# Heavy image with model snapshot for simulation
simulation_image = (
    modal.Image.debian_slim(python_version="3.13")
    .pip_install(
        f"policyengine-us=={US_VERSION}",
        f"policyengine-uk=={UK_VERSION}",
        f"policyengine=={POLICYENGINE_VERSION}",
        f"policyengine-core=={POLICYENGINE_CORE_VERSION}",
        "fastapi>=0.115.0",
        "tables>=3.10.2",
        "logfire",
    )
    .add_local_python_source(
        "src.modal",
        "policyengine_api_simulation",
        copy=True,
    )
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


@app.function(
    image=simulation_image,
    cpu=8.0,
    memory=32768,
    timeout=3600,
    retries=0,
    max_containers=100,
    secrets=[gcp_secret, data_secret, logfire_secret],
)
def run_simulation(params: dict) -> dict:
    """
    Execute economic simulation.

    Imports the snapshotted implementation at runtime.
    Logs input params and output result to Logfire for observability.
    """
    import logfire

    from policyengine_api_simulation.simulation_runtime import run_simulation_impl

    configure_logfire()

    # We deliberately avoid sending full ``params`` or ``result`` blobs to
    # Logfire: both can embed signed URLs, reform parameter trees with
    # sensitive policy details, or result payloads large enough to blow the
    # span attribute size budget. The redacted summary keeps correlation
    # traceability via run_id while leaving the heavy payload in memory.
    redacted_params = redact_params_for_logging(params)
    try:
        with logfire.span(
            "run_simulation",
            **redacted_params,
        ):
            return run_simulation_impl(params)
    finally:
        logfire.force_flush()


@app.function(
    image=simulation_image,
    cpu=1.0,
    memory=4096,
    timeout=3600,
    retries=0,
    max_containers=100,
    secrets=[gcp_secret, data_secret, logfire_secret],
)
def run_budget_window_batch(params: dict) -> dict:
    """Execute a multi-year budget-window batch orchestration."""
    import logfire

    from src.modal.budget_window_batch import run_budget_window_batch_impl

    configure_logfire()

    redacted_params = redact_params_for_logging(params)
    try:
        with logfire.span(
            "run_budget_window_batch",
            **redacted_params,
        ):
            return run_budget_window_batch_impl(params)
    finally:
        logfire.force_flush()
