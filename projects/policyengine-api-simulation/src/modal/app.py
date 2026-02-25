"""
PolicyEngine Simulation - Versioned Modal App

This app contains the heavy simulation workload with snapshotted models.
Each deployment creates a versioned app (e.g., policyengine-simulation-us1-459-0-uk2-65-9).

The gateway app (policyengine-simulation-gateway) routes requests to these versioned apps.
"""

import modal
import os

from src.modal._image_setup import snapshot_models

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
        "policyengine>=0.10.1,<1",
        "tables>=3.10.2",
        "logfire",
    )
    .add_local_python_source("src.modal", copy=True)
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
    max_containers=30,
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

    configure_logfire()

    try:
        with logfire.span(
            "run_simulation",
            input_params=params,
        ) as span:
            result = run_simulation_impl(params)
            span.set_attribute("output_result", result)
            return result
    finally:
        logfire.force_flush()
