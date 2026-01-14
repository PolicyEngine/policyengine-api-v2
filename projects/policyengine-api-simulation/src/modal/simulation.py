"""
Simulation implementation - pure logic with snapshotted imports.

This module has policyengine imports at module level so they are
captured in Modal's image snapshot. No Modal dependencies here.
"""

import json
import logging
import os
import tempfile

# Module-level imports - these are SNAPSHOTTED at image build time
from policyengine.simulation import Simulation, SimulationOptions

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


def run_simulation_impl(params: dict) -> dict:
    """
    Execute economic simulation.

    Pure implementation with no Modal dependencies.
    Accepts SimulationOptions as a dict and returns EconomyComparison as a dict.
    """
    # Set up GCP credentials if needed
    setup_gcp_credentials()

    logger.info(f"Starting simulation for country: {params.get('country', 'unknown')}")

    # Validate and create simulation options
    options = SimulationOptions.model_validate(params)
    logger.info("Initialising simulation from input")

    # Create simulation instance
    simulation = Simulation(**options.model_dump())
    logger.info("Calculating comparison")

    # Run the economy comparison calculation
    result = simulation.calculate_economy_comparison()
    logger.info("Comparison complete")

    # Use mode='json' to ensure numpy arrays are converted to lists
    return result.model_dump(mode="json")
