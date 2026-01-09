"""
PolicyEngine Simulation Gateway - Modal App Definition

Routes simulation requests to version-specific apps using
direct function dispatch. Handles job submission and status polling.
"""

import logging

import modal

from .endpoints import router

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = modal.App("policyengine-gateway")

# Lightweight image - no policyengine dependencies needed
gateway_image = modal.Image.debian_slim(python_version="3.13").pip_install(
    "fastapi>=0.115.0",
    "pydantic>=2.0",
)


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
        title="PolicyEngine Simulation Gateway",
        description="Routes simulation requests to version-specific backends",
        version="1.0.0",
    )

    api.include_router(router)

    return api
