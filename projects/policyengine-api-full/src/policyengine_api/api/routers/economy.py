# economy_simulation.py
from fastapi import APIRouter, Query, Body, HTTPException
from typing import Literal
from policyengine_api.api.services.simulation_runner import SimulationRunner

router = APIRouter()
runner = SimulationRunner()


@router.post("/{country_id}/economy/{policy_id}/over/{baseline_policy_id}")
async def start_simulation(
    country_id: str,
    policy_id: int,
    baseline_policy_id: int,
    region: str = Query(...),
    dataset: str = Query("default"),
    time_period: str = Query(...),
    target: Literal["general", "cliff"] = Query("general"),
    version: str | None = Query(None),
    reform: dict = Body(...),
    baseline: dict = Body(...),
):
    try:
        result = await runner.start_simulation(
            country_id=country_id,
            reform=reform,
            baseline=baseline,
            region=region,
            dataset=dataset,
            time_period=time_period,
            scope="macro",
            model_version=version,
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/economy/result")
async def get_simulation_result(execution_id: str):
    try:
        result = await runner.get_simulation_result(execution_id)
        print("SKLOGS: get api called")
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
