from fastapi import APIRouter, HTTPException, Depends, Query
from sqlmodel import Session, select
from policyengine.database import SimulationTable, Database
from policyengine.models import Simulation
from policyengine_api_full.database import get_session
from policyengine_api_full.schemas import SimulationResponse, SimulationCreate, SimulationDetailResponse, decode_bytes
from typing import Optional
from datetime import datetime
from uuid import uuid4
import os

router = APIRouter(prefix="/simulations", tags=["simulations"])


@router.get("/", response_model=list[SimulationResponse])
def list_simulations(
    session: Session = Depends(get_session),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    policy_id: Optional[str] = Query(None, description="Filter by policy ID"),
    dataset_id: Optional[str] = Query(None, description="Filter by dataset ID"),
    model_id: Optional[str] = Query(None, description="Filter by model ID"),
):
    """List all simulations with pagination and optional filters."""
    statement = select(SimulationTable)

    if policy_id:
        statement = statement.where(SimulationTable.policy_id == policy_id)
    if dataset_id:
        statement = statement.where(SimulationTable.dataset_id == dataset_id)
    if model_id:
        statement = statement.where(SimulationTable.model_id == model_id)

    statement = statement.offset(skip).limit(limit)
    simulations = session.exec(statement).all()
    return [SimulationResponse.from_orm(s) for s in simulations]


@router.post("/", response_model=SimulationResponse, status_code=201)
def create_simulation(
    simulation: SimulationCreate,
    session: Session = Depends(get_session),
    user_id: Optional[str] = Query(None, description="User ID to automatically associate with this simulation"),
):
    """Create a new simulation. It will be picked up by the queue worker for processing. Optionally associate with a user by passing user_id query param."""
    from policyengine_api_full.models import UserSimulationTable

    db_simulation = SimulationTable(
        id=str(uuid4()),
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
        **simulation.to_orm_dict()
    )
    session.add(db_simulation)
    session.commit()
    session.refresh(db_simulation)

    # Auto-create user association if user_id provided
    if user_id:
        user_simulation = UserSimulationTable(
            user_id=user_id,
            simulation_id=db_simulation.id,
            is_creator=True,
        )
        session.add(user_simulation)
        session.commit()

    # Simulation will be picked up by queue worker (no background task)
    return SimulationResponse.from_orm(db_simulation)


@router.get("/{simulation_id}", response_model=SimulationResponse)
def get_simulation(
    simulation_id: str,
    session: Session = Depends(get_session),
):
    """Get a single simulation by ID (without result data)."""
    simulation = session.get(SimulationTable, simulation_id)
    if not simulation:
        raise HTTPException(status_code=404, detail="Simulation not found")
    return SimulationResponse.from_orm(simulation)


@router.get("/{simulation_id}/result", response_model=SimulationDetailResponse)
def get_simulation_result(
    simulation_id: str,
    session: Session = Depends(get_session),
):
    """Get a single simulation by ID with full result data."""
    simulation = session.get(SimulationTable, simulation_id)
    if not simulation:
        raise HTTPException(status_code=404, detail="Simulation not found")
    return SimulationDetailResponse.from_orm(simulation)


@router.patch("/{simulation_id}", response_model=SimulationResponse)
def update_simulation(
    simulation_id: str,
    policy_id: Optional[str] = None,
    dynamic_id: Optional[str] = None,
    dataset_id: Optional[str] = None,
    model_id: Optional[str] = None,
    model_version_id: Optional[str] = None,
    result: Optional[str] = None,
    session: Session = Depends(get_session),
):
    """Update a simulation."""
    db_simulation = session.get(SimulationTable, simulation_id)
    if not db_simulation:
        raise HTTPException(status_code=404, detail="Simulation not found")

    if policy_id is not None:
        db_simulation.policy_id = policy_id
    if dynamic_id is not None:
        db_simulation.dynamic_id = dynamic_id
    if dataset_id is not None:
        db_simulation.dataset_id = dataset_id
    if model_id is not None:
        db_simulation.model_id = model_id
    if model_version_id is not None:
        db_simulation.model_version_id = model_version_id
    if result is not None:
        db_simulation.result = decode_bytes(result)

    db_simulation.updated_at = datetime.utcnow()

    session.add(db_simulation)
    session.commit()
    session.refresh(db_simulation)
    return SimulationResponse.from_orm(db_simulation)


@router.post("/{simulation_id}/run", response_model=SimulationResponse)
def run_simulation(
    simulation_id: str,
    session: Session = Depends(get_session),
):
    """Queue an existing simulation for processing by clearing its result."""
    simulation = session.get(SimulationTable, simulation_id)
    if not simulation:
        raise HTTPException(status_code=404, detail="Simulation not found")

    # Clear result to queue it for reprocessing
    simulation.result = None
    simulation.updated_at = datetime.utcnow()
    session.add(simulation)
    session.commit()
    session.refresh(simulation)

    return SimulationResponse.from_orm(simulation)


@router.delete("/{simulation_id}", status_code=204)
def delete_simulation(
    simulation_id: str,
    session: Session = Depends(get_session),
):
    """Delete a simulation."""
    simulation = session.get(SimulationTable, simulation_id)
    if not simulation:
        raise HTTPException(status_code=404, detail="Simulation not found")

    session.delete(simulation)
    session.commit()
    return None