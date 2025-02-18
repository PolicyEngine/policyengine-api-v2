from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from policyengine.simulation import SimulationOptions, Simulation
from policyengine.outputs.macro.comparison.calculate_economy_comparison import EconomyComparison


def create_router(session_dependency:SessionGeneratorFactory):
    router = APIRouter()
    
    @router.post("/simulate")
    async def create_houshold(parameters:SimulationOptions)->EconomyComparison:
        model = SimulationOptions.model_validate(item)

        simulation = Simulation(**model.model_dump())
        
        return simulation.calculate_economy_comparison()

    return router