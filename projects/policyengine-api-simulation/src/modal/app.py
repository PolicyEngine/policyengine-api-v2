"""
PolicyEngine Simulation - Modal App Definition

Defines the Modal app and container image configuration.
"""

import modal
import logging
import os

from .utils import snapshot_models

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = modal.App("policyengine-simulation")

# Get versions from environment or use defaults from pyproject.toml
US_VERSION = os.environ.get("POLICYENGINE_US_VERSION", "1.370.2")
UK_VERSION = os.environ.get("POLICYENGINE_UK_VERSION", "2.22.8")

# Build image with model snapshot for sub-1s cold starts
image = (
    modal.Image.debian_slim(python_version="3.13")
    .pip_install(
        "policyengine>=0.8.1",
        f"policyengine-us>={US_VERSION}",
        f"policyengine-uk>={UK_VERSION}",
        "tables>=3.10.2",
    )
    .run_function(snapshot_models)  # Snapshot loaded models into image
)

# Import jobs to register them with the app
from .jobs import run_simulation

__all__ = ["app", "image", "run_simulation"]
