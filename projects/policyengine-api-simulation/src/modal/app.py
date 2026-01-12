"""
PolicyEngine Simulation - Modal App Definition

All Modal wiring in one place. This file is only fully processed at deploy time.
At runtime, containers just execute the snapshotted simulation code.
"""

import modal
import os

from src.modal._image_setup import snapshot_models

# App definition
app = modal.App("policyengine-simulation")

# Get versions from environment or use defaults
US_VERSION = os.environ.get("POLICYENGINE_US_VERSION", "1.459.0")
UK_VERSION = os.environ.get("POLICYENGINE_UK_VERSION", "2.65.9")

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
        "policyengine==0.8.1",
        "tables>=3.10.2",
        "logfire",
    )
    .add_local_python_source("src.modal", copy=True)
    .run_function(snapshot_models)
)

# Lightweight image for gateway
gateway_image = (
    modal.Image.debian_slim(python_version="3.13")
    .pip_install(
        "fastapi>=0.115.0",
        "pydantic>=2.0",
    )
    .add_local_python_source("src.modal", copy=True)
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


@app.function(image=gateway_image)
@modal.asgi_app()
def web_app():
    """
    FastAPI gateway for simulation job submission and polling.
    """
    from fastapi import FastAPI
    from src.modal.gateway.endpoints import router

    api = FastAPI(
        title="PolicyEngine Simulation API",
        description="Submit and poll simulation jobs",
        version="1.0.0",
    )
    api.include_router(router)
    return api
