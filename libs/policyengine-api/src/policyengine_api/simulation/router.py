from fastapi import APIRouter, Depends, HTTPException, status
from typing import Annotated
from sqlmodel import Session
from policyengine_fastapi.auth import JWTDecoder
from policyengine_fastapi.database import SessionGeneratorFactory
from .models import SimulationJob
import json
from datetime import datetime
import logging
from policyengine import Simulation

LOG = logging.getLogger(__name__)


def create_simulation_router(
    session_dependency: SessionGeneratorFactory,
    optional_auth: JWTDecoder,
    auth: JWTDecoder,
) -> APIRouter:
    router = APIRouter(tags=["Simulation"])

    @router.post("/{job_id}/run", response_model=SimulationJob)
    def run_simulation(
        job_id: int,
        session: Annotated[Session, Depends(session_dependency)],
        token=Depends(auth),  # Require valid auth token for this operation.
    ):
        # Retrieve the job from the database.
        job = session.get(SimulationJob, job_id)
        if not job:
            raise HTTPException(
                status_code=404, detail="SimulationJob not found"
            )

        # Ensure there is input data to process.
        if not job.input_data:
            raise HTTPException(
                status_code=400,
                detail="No input data available for simulation",
            )

        try:
            input_data = json.loads(job.input_data)
        except Exception as e:
            LOG.error(f"Invalid input data format for job {job_id}: {e}")
            raise HTTPException(
                status_code=400, detail="Invalid input data format"
            )

        # Run the simulation synchronously.
        try:
            sim = Simulation(input_data)
            simulation_result = sim.calculate()
        except Exception as e:
            LOG.error(f"Simulation execution failed for job {job_id}: {e}")
            raise HTTPException(
                status_code=500, detail="Simulation execution failed"
            )

        # Update the job with the simulation output.
        try:
            job.output_data = json.dumps(simulation_result)
        except Exception as e:
            LOG.error(
                f"Failed to serialize simulation result for job {job_id}: {e}"
            )
            raise HTTPException(
                status_code=500, detail="Failed to serialize simulation result"
            )

        job.status = "complete"
        job.completed_at = datetime.utcnow()

        session.add(job)
        session.commit()
        session.refresh(job)
        return job

    return router
