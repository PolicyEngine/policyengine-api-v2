import logging

from fastapi import APIRouter

from policyengine_api_simulation.simulation_runtime import run_simulation_impl
from policyengine_api_simulation.compat_models import (
    EconomyComparison,
    SimulationOptions,
)

logger = logging.getLogger(__file__)


def create_router():
    router = APIRouter()

    @router.post("/simulate/economy/comparison", response_model=EconomyComparison)
    async def simulate(parameters: SimulationOptions) -> EconomyComparison:
        logger.info("Calculating comparison")
        result = run_simulation_impl(
            parameters.model_dump(mode="json", exclude_none=True)
        )
        logger.info("Comparison complete")
        return EconomyComparison.model_validate(result)

    return router
