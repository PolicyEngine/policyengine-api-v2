"""
Simulation job - runs economic comparison simulations.
"""

import logging

from ..app import app, image

logger = logging.getLogger(__name__)


@app.function(
    image=image,
    cpu=8.0,
    memory=32768,  # 32 GiB
    timeout=3600,  # 1 hour
    retries=0,
)
def run_simulation(params: dict) -> dict:
    """
    Execute economic simulation.

    Called via gateway's direct function dispatch.
    Returns dict for JSON serialization.
    """
    from policyengine.simulation import Simulation, SimulationOptions

    logger.info(f"Starting simulation for country: {params.get('country', 'unknown')}")

    options = SimulationOptions.model_validate(params)
    simulation = Simulation(**options.model_dump())
    result = simulation.calculate_economy_comparison()

    logger.info("Simulation complete")
    return result.model_dump()
