from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from policyengine.simulation import SimulationOptions, Simulation
from policyengine.outputs.macro.comparison.calculate_economy_comparison import (
    EconomyComparison,
)


def create_router():
    router = APIRouter()

    @router.post("/simulate/economy/comparison", response_model=EconomyComparison)
    async def simulate(parameters: SimulationOptions) -> EconomyComparison:
        print(parameters)
        model = SimulationOptions.model_validate(parameters)

        simulation = Simulation(**model.model_dump())

        return simulation.calculate_economy_comparison()

    return router
