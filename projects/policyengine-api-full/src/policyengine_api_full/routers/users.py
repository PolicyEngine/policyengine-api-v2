"""User management endpoints."""

from fastapi import APIRouter, HTTPException, Depends, Query
from sqlmodel import Session, select
from typing import List
from pydantic import BaseModel
from policyengine_api_full.models import (
    UserTable,
    UserReportTable,
    ReportTable,
    UserPolicyTable,
    UserDatasetTable,
    UserSimulationTable,
)
from policyengine.database import PolicyTable, DatasetTable, SimulationTable
from policyengine_api_full.database import get_session

router = APIRouter(prefix="/users", tags=["users"])


class UserResponse(BaseModel):
    id: str
    username: str
    first_name: str | None
    last_name: str | None
    email: str | None
    current_model_id: str
    created_at: str
    updated_at: str


class UserDetailResponse(BaseModel):
    """User details with counts of associated resources."""

    id: str
    username: str
    first_name: str | None
    last_name: str | None
    email: str | None
    current_model_id: str
    created_at: str
    updated_at: str
    reports_count: int
    policies_count: int
    datasets_count: int
    simulations_count: int


class UserCreate(BaseModel):
    username: str
    first_name: str | None = None
    last_name: str | None = None
    email: str | None = None


class UserUpdate(BaseModel):
    username: str | None = None
    first_name: str | None = None
    last_name: str | None = None
    email: str | None = None
    current_model_id: str | None = None


@router.get("", response_model=List[UserResponse])
async def list_users(db: Session = Depends(get_session)):
    """List all users."""
    users = db.exec(select(UserTable)).all()

    return [
        UserResponse(
            id=user.id,
            username=user.username,
            first_name=user.first_name,
            last_name=user.last_name,
            email=user.email,
            current_model_id=user.current_model_id,
            created_at=user.created_at.isoformat(),
            updated_at=user.updated_at.isoformat(),
        )
        for user in users
    ]


@router.get("/{user_id}", response_model=UserDetailResponse)
async def get_user(user_id: str, db: Session = Depends(get_session)):
    """Get a specific user with collated resource counts."""
    user = db.get(UserTable, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Get counts of associated resources
    reports_count = len(
        db.exec(select(UserReportTable).where(UserReportTable.user_id == user_id)).all()
    )

    policies_count = len(
        db.exec(select(UserPolicyTable).where(UserPolicyTable.user_id == user_id)).all()
    )

    datasets_count = len(
        db.exec(
            select(UserDatasetTable).where(UserDatasetTable.user_id == user_id)
        ).all()
    )

    simulations_count = len(
        db.exec(
            select(UserSimulationTable).where(UserSimulationTable.user_id == user_id)
        ).all()
    )

    return UserDetailResponse(
        id=user.id,
        username=user.username,
        first_name=user.first_name,
        last_name=user.last_name,
        email=user.email,
        current_model_id=user.current_model_id,
        created_at=user.created_at.isoformat(),
        updated_at=user.updated_at.isoformat(),
        reports_count=reports_count,
        policies_count=policies_count,
        datasets_count=datasets_count,
        simulations_count=simulations_count,
    )


@router.post("", response_model=UserResponse)
async def create_user(data: UserCreate, db: Session = Depends(get_session)):
    """Create a new user."""
    user = UserTable(
        username=data.username,
        first_name=data.first_name,
        last_name=data.last_name,
        email=data.email,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    return UserResponse(
        id=user.id,
        username=user.username,
        first_name=user.first_name,
        last_name=user.last_name,
        email=user.email,
        current_model_id=user.current_model_id,
        created_at=user.created_at.isoformat(),
        updated_at=user.updated_at.isoformat(),
    )


@router.patch("/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: str, data: UserUpdate, db: Session = Depends(get_session)
):
    """Update a user."""
    user = db.get(UserTable, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if data.username is not None:
        user.username = data.username
    if data.first_name is not None:
        user.first_name = data.first_name
    if data.last_name is not None:
        user.last_name = data.last_name
    if data.email is not None:
        user.email = data.email
    if data.current_model_id is not None:
        user.current_model_id = data.current_model_id

    db.add(user)
    db.commit()
    db.refresh(user)

    return UserResponse(
        id=user.id,
        username=user.username,
        first_name=user.first_name,
        last_name=user.last_name,
        email=user.email,
        current_model_id=user.current_model_id,
        created_at=user.created_at.isoformat(),
        updated_at=user.updated_at.isoformat(),
    )


@router.delete("/{user_id}")
async def delete_user(user_id: str, db: Session = Depends(get_session)):
    """Delete a user."""
    user = db.get(UserTable, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    db.delete(user)
    db.commit()

    return {"message": "User deleted"}


# User sub-resources


@router.get("/{user_id}/reports", response_model=List[ReportTable])
async def get_user_reports(
    user_id: str,
    db: Session = Depends(get_session),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=10_000),
):
    """Get all reports for a user."""
    user = db.get(UserTable, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Get report IDs for this user
    user_reports = db.exec(
        select(UserReportTable)
        .where(UserReportTable.user_id == user_id)
        .offset(skip)
        .limit(limit)
    ).all()

    if not user_reports:
        return []

    report_ids = [ur.report_id for ur in user_reports]
    reports = db.exec(select(ReportTable).where(ReportTable.id.in_(report_ids))).all()

    return reports


@router.get("/{user_id}/policies", response_model=List[PolicyTable])
async def get_user_policies(
    user_id: str,
    db: Session = Depends(get_session),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=10_000),
):
    """Get all policies for a user."""
    user = db.get(UserTable, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Get policy IDs for this user
    user_policies = db.exec(
        select(UserPolicyTable)
        .where(UserPolicyTable.user_id == user_id)
        .offset(skip)
        .limit(limit)
    ).all()

    if not user_policies:
        return []

    policy_ids = [up.policy_id for up in user_policies]
    policies = db.exec(select(PolicyTable).where(PolicyTable.id.in_(policy_ids))).all()

    return policies


@router.get("/{user_id}/datasets", response_model=List[DatasetTable])
async def get_user_datasets(
    user_id: str,
    db: Session = Depends(get_session),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=10_000),
):
    """Get all datasets for a user."""
    user = db.get(UserTable, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Get dataset IDs for this user
    user_datasets = db.exec(
        select(UserDatasetTable)
        .where(UserDatasetTable.user_id == user_id)
        .offset(skip)
        .limit(limit)
    ).all()

    if not user_datasets:
        return []

    dataset_ids = [ud.dataset_id for ud in user_datasets]
    datasets = db.exec(
        select(DatasetTable).where(DatasetTable.id.in_(dataset_ids))
    ).all()

    return datasets


@router.get("/{user_id}/simulations", response_model=List[SimulationTable])
async def get_user_simulations(
    user_id: str,
    db: Session = Depends(get_session),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=10_000),
):
    """Get all simulations for a user."""
    user = db.get(UserTable, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Get simulation IDs for this user
    user_simulations = db.exec(
        select(UserSimulationTable)
        .where(UserSimulationTable.user_id == user_id)
        .offset(skip)
        .limit(limit)
    ).all()

    if not user_simulations:
        return []

    simulation_ids = [us.simulation_id for us in user_simulations]
    simulations = db.exec(
        select(SimulationTable).where(SimulationTable.id.in_(simulation_ids))
    ).all()

    return simulations
