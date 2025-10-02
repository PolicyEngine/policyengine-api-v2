"""User simulation management endpoints."""
from fastapi import APIRouter, HTTPException, Depends
from sqlmodel import Session, select
from typing import List
from pydantic import BaseModel
from policyengine.database import UserSimulationTable
from policyengine_api_full.database import get_session

router = APIRouter(prefix="/user-simulations", tags=["user simulations"])


class UserSimulationCreate(BaseModel):
    user_id: str
    simulation_id: str
    custom_name: str | None = None


class UserSimulationUpdate(BaseModel):
    custom_name: str


class UserSimulationResponse(BaseModel):
    id: str
    user_id: str
    simulation_id: str
    custom_name: str | None
    created_at: str
    updated_at: str


@router.post("", response_model=UserSimulationResponse)
async def create_user_simulation(
    data: UserSimulationCreate,
    db: Session = Depends(get_session)
):
    """Create a user simulation link."""
    user_sim = UserSimulationTable(
        user_id=data.user_id,
        simulation_id=data.simulation_id,
        custom_name=data.custom_name,
    )
    db.add(user_sim)
    db.commit()
    db.refresh(user_sim)

    return UserSimulationResponse(
        id=user_sim.id,
        user_id=user_sim.user_id,
        simulation_id=user_sim.simulation_id,
        custom_name=user_sim.custom_name,
        created_at=user_sim.created_at.isoformat(),
        updated_at=user_sim.updated_at.isoformat(),
    )


@router.get("", response_model=List[UserSimulationResponse])
async def list_user_simulations(
    user_id: str,
    db: Session = Depends(get_session)
):
    """List all simulations for a user."""
    user_sims = db.exec(
        select(UserSimulationTable).where(UserSimulationTable.user_id == user_id)
    ).all()

    return [
        UserSimulationResponse(
            id=us.id,
            user_id=us.user_id,
            simulation_id=us.simulation_id,
            custom_name=us.custom_name,
            created_at=us.created_at.isoformat(),
            updated_at=us.updated_at.isoformat(),
        )
        for us in user_sims
    ]


@router.get("/{user_sim_id}", response_model=UserSimulationResponse)
async def get_user_simulation(
    user_sim_id: str,
    db: Session = Depends(get_session)
):
    """Get a specific user simulation."""
    user_sim = db.get(UserSimulationTable, user_sim_id)
    if not user_sim:
        raise HTTPException(status_code=404, detail="User simulation not found")

    return UserSimulationResponse(
        id=user_sim.id,
        user_id=user_sim.user_id,
        simulation_id=user_sim.simulation_id,
        custom_name=user_sim.custom_name,
        created_at=user_sim.created_at.isoformat(),
        updated_at=user_sim.updated_at.isoformat(),
    )


@router.patch("/{user_sim_id}", response_model=UserSimulationResponse)
async def update_user_simulation(
    user_sim_id: str,
    data: UserSimulationUpdate,
    db: Session = Depends(get_session)
):
    """Update a user simulation's custom name."""
    user_sim = db.get(UserSimulationTable, user_sim_id)
    if not user_sim:
        raise HTTPException(status_code=404, detail="User simulation not found")

    user_sim.custom_name = data.custom_name
    db.add(user_sim)
    db.commit()
    db.refresh(user_sim)

    return UserSimulationResponse(
        id=user_sim.id,
        user_id=user_sim.user_id,
        simulation_id=user_sim.simulation_id,
        custom_name=user_sim.custom_name,
        created_at=user_sim.created_at.isoformat(),
        updated_at=user_sim.updated_at.isoformat(),
    )


@router.delete("/{user_sim_id}")
async def delete_user_simulation(
    user_sim_id: str,
    db: Session = Depends(get_session)
):
    """Delete a user simulation link."""
    user_sim = db.get(UserSimulationTable, user_sim_id)
    if not user_sim:
        raise HTTPException(status_code=404, detail="User simulation not found")

    db.delete(user_sim)
    db.commit()

    return {"message": "User simulation deleted"}