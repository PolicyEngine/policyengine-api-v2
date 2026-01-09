"""
Modal app and image configuration.

This module defines the core Modal app and images, separate from
function definitions to avoid circular imports.
"""

import modal
import logging
import os

from ._image_setup import snapshot_models

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = modal.App("policyengine-sim")

# Get versions from environment or use defaults
US_VERSION = os.environ.get("POLICYENGINE_US_VERSION", "1.370.2")
UK_VERSION = os.environ.get("POLICYENGINE_UK_VERSION", "2.22.8")

# Heavy image with model snapshot for simulation (sub-1s cold starts)
simulation_image = (
    modal.Image.debian_slim(python_version="3.13")
    .pip_install(
        "policyengine>=0.8.1",
        f"policyengine-us>={US_VERSION}",
        f"policyengine-uk>={UK_VERSION}",
        "tables>=3.10.2",
    )
    .run_function(snapshot_models)
)

# Lightweight image for gateway (no policyengine dependencies)
gateway_image = modal.Image.debian_slim(python_version="3.13").pip_install(
    "fastapi>=0.115.0",
    "pydantic>=2.0",
)
