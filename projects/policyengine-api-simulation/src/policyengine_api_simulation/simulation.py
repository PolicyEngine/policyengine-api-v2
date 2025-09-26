import os
from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel
import logging
from policyengine.database import Database
from policyengine.models import Policy, Dynamic, Model, ModelVersion, Dataset, Simulation
from typing import Optional
from uuid import uuid4
from datetime import datetime

logger = logging.getLogger(__file__)

# Initialize database connection
database = Database(url=os.environ.get("DATABASE_URL", "postgresql://postgres:postgres@127.0.0.1:54322/postgres"))


class SimulationCreateRequest(BaseModel):
    """Request model for creating a simulation."""
    policy_id: Optional[str] = None
    dynamic_id: Optional[str] = None
    dataset_id: str
    model_id: str
    model_version_id: Optional[str] = None


class SimulationCreateResponse(BaseModel):
    """Response model for simulation creation."""
    simulation_id: str
    status: str
    message: str


class SimulationRunRequest(BaseModel):
    """Request model for running a simulation."""
    simulation_id: str


class SimulationRunResponse(BaseModel):
    """Response model for simulation run."""
    simulation_id: str
    status: str
    message: str


def run_simulation_task(simulation_id: str):
    """Background task to run a simulation."""
    try:
        logger.info(f"Fetching simulation {simulation_id} from database")
        simulation = database.get(Simulation, id=simulation_id)

        if not simulation:
            logger.error(f"Simulation {simulation_id} not found")
            return

        logger.info(f"Running simulation {simulation_id}")
        simulation.run()

        logger.info(f"Saving simulation results for {simulation_id}")
        database.set(simulation)

        logger.info(f"Successfully completed simulation {simulation_id}")
    except Exception as e:
        logger.error(f"Error running simulation {simulation_id}: {e}")


def create_router():
    router = APIRouter()

    @router.post("/create_simulation", response_model=SimulationCreateResponse)
    async def create_simulation(
        request: SimulationCreateRequest,
    ) -> SimulationCreateResponse:
        """
        Create a new simulation in the database.
        """
        try:
            # Generate a new simulation ID
            simulation_id = str(uuid4())

            # Fetch the required objects from database
            policy = database.get(Policy, id=request.policy_id) if request.policy_id else None
            dynamic = database.get(Dynamic, id=request.dynamic_id) if request.dynamic_id else None
            dataset = database.get(Dataset, id=request.dataset_id)
            model = database.get(Model, id=request.model_id)
            model_version = database.get(ModelVersion, id=request.model_version_id) if request.model_version_id else None

            if not dataset:
                raise HTTPException(status_code=404, detail=f"Dataset {request.dataset_id} not found")
            if not model:
                raise HTTPException(status_code=404, detail=f"Model {request.model_id} not found")

            # Create the simulation object
            simulation = Simulation(
                id=simulation_id,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
                policy=policy,
                dynamic=dynamic,
                dataset=dataset,
                model=model,
                model_version=model_version,
                result=None
            )

            # Save to database
            logger.info(f"Creating simulation {simulation_id} in database")
            database.set(simulation)

            return SimulationCreateResponse(
                simulation_id=simulation_id,
                status="created",
                message=f"Simulation {simulation_id} created successfully"
            )
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error creating simulation: {e}")
            raise HTTPException(status_code=500, detail=f"Error creating simulation: {str(e)}")

    @router.post("/create_and_run_simulation", response_model=SimulationCreateResponse)
    async def create_and_run_simulation(
        request: SimulationCreateRequest,
        background_tasks: BackgroundTasks
    ) -> SimulationCreateResponse:
        """
        Create a new simulation and immediately run it.
        This combines creation and execution in one step.
        """
        try:
            # Generate a new simulation ID
            simulation_id = str(uuid4())

            # Fetch the required objects from database
            policy = database.get(Policy, id=request.policy_id) if request.policy_id else None
            dynamic = database.get(Dynamic, id=request.dynamic_id) if request.dynamic_id else None
            dataset = database.get(Dataset, id=request.dataset_id)
            model = database.get(Model, id=request.model_id)
            model_version = database.get(ModelVersion, id=request.model_version_id) if request.model_version_id else None

            if not dataset:
                raise HTTPException(status_code=404, detail=f"Dataset {request.dataset_id} not found")
            if not model:
                raise HTTPException(status_code=404, detail=f"Model {request.model_id} not found")

            # Create the simulation object
            simulation = Simulation(
                id=simulation_id,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
                policy=policy,
                dynamic=dynamic,
                dataset=dataset,
                model=model,
                model_version=model_version,
                result=None
            )

            # Save to database
            logger.info(f"Creating simulation {simulation_id} in database")
            database.set(simulation)

            # Add background task to run the simulation
            background_tasks.add_task(run_simulation_task, simulation_id)

            return SimulationCreateResponse(
                simulation_id=simulation_id,
                status="running",
                message=f"Simulation {simulation_id} created and running in background"
            )
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error creating and running simulation: {e}")
            raise HTTPException(status_code=500, detail=f"Error creating and running simulation: {str(e)}")

    @router.post("/run_simulation", response_model=SimulationRunResponse)
    async def run_simulation(
        request: SimulationRunRequest,
        background_tasks: BackgroundTasks
    ) -> SimulationRunResponse:
        """
        Run an existing simulation by ID using the database pattern from test.py.
        The simulation runs in the background.
        """
        simulation_id = request.simulation_id

        # Verify simulation exists
        try:
            simulation = database.get(Simulation, id=simulation_id)
            if not simulation:
                raise HTTPException(status_code=404, detail=f"Simulation {simulation_id} not found")
        except Exception as e:
            logger.error(f"Error fetching simulation {simulation_id}: {e}")
            raise HTTPException(status_code=500, detail=f"Error fetching simulation: {str(e)}")

        # Add background task to run the simulation
        background_tasks.add_task(run_simulation_task, simulation_id)

        return SimulationRunResponse(
            simulation_id=simulation_id,
            status="running",
            message=f"Simulation {simulation_id} is running in the background"
        )

    @router.post("/run_simulation_sync/{simulation_id}")
    async def run_simulation_sync(simulation_id: str) -> dict:
        """
        Run a simulation synchronously (blocking).
        This follows the exact pattern from test.py.
        """
        try:
            # Fetch simulation from database
            logger.info(f"Fetching simulation {simulation_id} from database")
            simulation = database.get(Simulation, id=simulation_id)

            if not simulation:
                raise HTTPException(status_code=404, detail=f"Simulation {simulation_id} not found")

            # Run the simulation
            logger.info(f"Running simulation {simulation_id}")
            simulation.run()

            # Save the results back to database
            logger.info(f"Saving simulation results for {simulation_id}")
            database.set(simulation)

            return {
                "simulation_id": simulation_id,
                "status": "completed",
                "message": f"Simulation {simulation_id} completed successfully"
            }
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error running simulation {simulation_id}: {e}")
            raise HTTPException(status_code=500, detail=f"Error running simulation: {str(e)}")

    @router.get("/simulation/{simulation_id}/status")
    async def get_simulation_status(simulation_id: str) -> dict:
        """
        Get the status of a simulation.
        """
        try:
            simulation = database.get(Simulation, id=simulation_id)

            if not simulation:
                raise HTTPException(status_code=404, detail=f"Simulation {simulation_id} not found")

            # Check if simulation has results
            has_results = simulation.result is not None

            return {
                "simulation_id": simulation_id,
                "has_results": has_results,
                "status": "completed" if has_results else "pending"
            }
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error fetching simulation status for {simulation_id}: {e}")
            raise HTTPException(status_code=500, detail=f"Error fetching simulation status: {str(e)}")

    return router