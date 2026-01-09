"""
PolicyEngine Simulation - Modal App Definition

Defines the Modal app with both simulation function and gateway web endpoint.
"""

import modal

from .config import app, gateway_image, simulation_image

# Import simulation job to register it with the app
from .jobs import run_simulation

# Import gateway components
from .gateway.endpoints import router


@app.function(image=gateway_image)
@modal.asgi_app(requires_proxy_auth=True)
def web_app():
    """
    FastAPI gateway for simulation job submission and polling.

    Uses direct function dispatch to call simulation functions
    in version-specific apps.
    """
    from fastapi import FastAPI

    api = FastAPI(
        title="PolicyEngine Simulation API",
        description="Submit and poll simulation jobs",
        version="1.0.0",
    )

    api.include_router(router)

    return api


__all__ = ["app", "simulation_image", "gateway_image", "run_simulation", "web_app"]
