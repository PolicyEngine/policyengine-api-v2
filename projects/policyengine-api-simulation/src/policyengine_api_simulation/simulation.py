from typing import Annotated
import os
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from policyengine.simulation import SimulationOptions, Simulation
from policyengine.outputs.macro.comparison.calculate_economy_comparison import (
    EconomyComparison,
)
from pathlib import Path
import logging

logger = logging.getLogger(__file__)


def create_router():
    router = APIRouter()

    @router.post("/simulate/economy/comparison", response_model=EconomyComparison)
    async def simulate(parameters: SimulationOptions) -> EconomyComparison:
        model = SimulationOptions.model_validate(parameters)
        logger.info("Initialising simulation from input")
        simulation = Simulation(**model.model_dump())
        logger.info("Calculating comparison")
        result = (
            simulation.calculate_economy_comparison()  # pyright: ignore [reportAttributeAccessIssue]
        )
        logger.info("Comparison complete")

        return result

    return router
