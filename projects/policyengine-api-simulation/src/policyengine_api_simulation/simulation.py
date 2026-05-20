import logging

from fastapi import APIRouter

from src.modal.simulation import run_simulation_impl

logger = logging.getLogger(__file__)


def create_router():
    router = APIRouter()

    @router.post("/simulate/economy/comparison", response_model=dict)
    async def simulate(parameters: dict) -> dict:
        logger.info("Calculating comparison")
        result = run_simulation_impl(parameters)
        logger.info("Comparison complete")
        return result

    return router
