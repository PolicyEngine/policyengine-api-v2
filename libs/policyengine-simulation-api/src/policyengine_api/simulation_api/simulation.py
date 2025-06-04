from fastapi import APIRouter
from policyengine.simulation import SimulationOptions, Simulation
from policyengine.outputs.macro.comparison.calculate_economy_comparison import (
    EconomyComparison,
)
from policyengine_api.simulation_api.utils.gcp_logging import logger


def create_router():
    router = APIRouter()

    @router.post(
        "/simulate/economy/comparison", response_model=EconomyComparison
    )
    async def simulate(parameters: SimulationOptions) -> EconomyComparison:
        model = SimulationOptions.model_validate(parameters)
        logger.log_struct(
            {
                "message": "Initializing economy comparison simulation",
                "parameters": parameters.model_dump(),
            }
        )
        simulation = Simulation(**model.model_dump())
        logger.log_struct(
            {
                "message": "Running economy comparison simulation",
                "parameters": parameters.model_dump(),
            }
        )
        result = simulation.calculate_economy_comparison()
        logger.log_struct(
            {
                "message": "Economy comparison simulation completed",
                "result": result,
            }
        )

        return result

    return router
