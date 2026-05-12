from typing import Annotated
import os
from fastapi import APIRouter, Depends, HTTPException
from pathlib import Path
import logging

try:
    from modal.simulation import run_simulation_impl
except ModuleNotFoundError:
    from src.modal.simulation import run_simulation_impl

logger = logging.getLogger(__file__)


def create_router():
    router = APIRouter()

    @router.post("/simulate/economy/comparison", response_model=dict)
    async def simulate(parameters: dict) -> dict:
        logger.info("Calculating comparison")
        return run_simulation_impl(parameters)

    return router
