"""
Simulation job - runs economic comparison simulations.
"""

import logging

from ..config import app, simulation_image

logger = logging.getLogger(__name__)


@app.function(
    image=simulation_image,
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
    logger.info(f"Starting simulation for country: {params.get('country', 'unknown')}")

    # TODO: Implement actual simulation logic
    # from policyengine.simulation import Simulation, SimulationOptions
    # options = SimulationOptions.model_validate(params)
    # simulation = Simulation(**options.model_dump())
    # result = simulation.calculate_economy_comparison()
    # return result.model_dump()

    result = {
        "status": "placeholder",
        "message": "Simulation placeholder - not yet implemented",
        "params_received": params,
    }

    logger.info("Simulation complete (placeholder)")
    return result
