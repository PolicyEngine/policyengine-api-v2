"""User management endpoints."""

from datetime import datetime
from fastapi import APIRouter, HTTPException, Depends, Query
from sqlmodel import Session, select
from typing import List, Optional
from pydantic import BaseModel
from policyengine_api_full.models import (
    UserTable,
    UserReportTable,
    ReportTable,
    UserPolicyTable,
    UserDatasetTable,
    UserSimulationTable,
    UserDynamicTable,
)
from policyengine.database import PolicyTable, DatasetTable, SimulationTable, DynamicTable
from policyengine_api_full.database import get_session
from policyengine_api_full.auth import get_current_user_id

router = APIRouter(prefix="/users", tags=["users"])


def verify_user_access(requested_user_id: str, auth_user_id: str) -> None:
    """Verify that the authenticated user matches the requested user ID."""
    if auth_user_id != requested_user_id:
        raise HTTPException(
            status_code=403,
            detail=f"Not authorized to access user {requested_user_id}",
        )


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
    """User details with associated resources."""

    id: str
    username: str
    first_name: str | None
    last_name: str | None
    email: str | None
    current_model_id: str
    created_at: str
    updated_at: str
    reports: list
    policies: list
    datasets: list
    simulations: list
    dynamics: list


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
    """Get a specific user with all associated resources. Auto-creates user if they don't exist."""
    user = db.get(UserTable, user_id)
    if not user:
        # Auto-create user if they don't exist (for Supabase auth users)
        user = UserTable(
            id=user_id,
            username=f"user_{user_id[:8]}",
            first_name=None,
            last_name=None,
            email=None,
        )
        db.add(user)
        db.commit()
        db.refresh(user)

    # Get resource IDs
    user_reports = db.exec(
        select(UserReportTable).where(UserReportTable.user_id == user_id)
    ).all()

    user_policies = db.exec(
        select(UserPolicyTable).where(UserPolicyTable.user_id == user_id)
    ).all()

    user_datasets = db.exec(
        select(UserDatasetTable).where(UserDatasetTable.user_id == user_id)
    ).all()

    user_simulations = db.exec(
        select(UserSimulationTable).where(UserSimulationTable.user_id == user_id)
    ).all()

    user_dynamics = db.exec(
        select(UserDynamicTable).where(UserDynamicTable.user_id == user_id)
    ).all()

    reports = [ur.report_id for ur in user_reports]
    policies = [up.policy_id for up in user_policies]
    datasets = [ud.dataset_id for ud in user_datasets]
    simulations = [us.simulation_id for us in user_simulations]
    dynamics = [ud.dynamic_id for ud in user_dynamics]

    return UserDetailResponse(
        id=user.id,
        username=user.username,
        first_name=user.first_name,
        last_name=user.last_name,
        email=user.email,
        current_model_id=user.current_model_id,
        created_at=user.created_at.isoformat(),
        updated_at=user.updated_at.isoformat(),
        reports=reports,
        policies=policies,
        datasets=datasets,
        simulations=simulations,
        dynamics=dynamics,
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


class UserReportResponse(BaseModel):
    id: str
    user_id: str
    report_id: str
    custom_name: str | None
    is_creator: bool
    created_at: str
    updated_at: str


class UserReportCreate(BaseModel):
    report_id: str
    custom_name: str | None = None


class UserReportUpdate(BaseModel):
    custom_name: str


@router.get("/{user_id}/reports", response_model=List[UserReportResponse])
async def get_user_reports(
    user_id: str,
    db: Session = Depends(get_session),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=10_000),
):
    """Get all report associations for a user."""
    user = db.get(UserTable, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    user_reports = db.exec(
        select(UserReportTable)
        .where(UserReportTable.user_id == user_id)
        .offset(skip)
        .limit(limit)
    ).all()

    return [
        UserReportResponse(
            id=ur.id,
            user_id=ur.user_id,
            report_id=ur.report_id,
            custom_name=ur.custom_name,
            is_creator=ur.is_creator,
            created_at=ur.created_at.isoformat(),
            updated_at=ur.updated_at.isoformat(),
        )
        for ur in user_reports
    ]


@router.post("/{user_id}/reports", response_model=UserReportResponse)
async def create_user_report(
    user_id: str,
    data: UserReportCreate,
    db: Session = Depends(get_session),
):
    """Create a user-report association (bookmark a report)."""
    user = db.get(UserTable, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Check if report exists
    report = db.get(ReportTable, data.report_id)
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")

    # Check if association already exists
    existing = db.exec(
        select(UserReportTable)
        .where(UserReportTable.user_id == user_id)
        .where(UserReportTable.report_id == data.report_id)
    ).first()

    if existing:
        raise HTTPException(
            status_code=400, detail="User already has association with this report"
        )

    user_report = UserReportTable(
        user_id=user_id,
        report_id=data.report_id,
        custom_name=data.custom_name,
        is_creator=False,  # Manual bookmarks are not creator associations
    )
    db.add(user_report)
    db.commit()
    db.refresh(user_report)

    return UserReportResponse(
        id=user_report.id,
        user_id=user_report.user_id,
        report_id=user_report.report_id,
        custom_name=user_report.custom_name,
        is_creator=user_report.is_creator,
        created_at=user_report.created_at.isoformat(),
        updated_at=user_report.updated_at.isoformat(),
    )


@router.patch("/{user_id}/reports/{report_id}", response_model=UserReportResponse)
async def update_user_report(
    user_id: str,
    report_id: str,
    data: UserReportUpdate,
    db: Session = Depends(get_session),
):
    """Update a user-report association."""
    user_report = db.exec(
        select(UserReportTable)
        .where(UserReportTable.user_id == user_id)
        .where(UserReportTable.report_id == report_id)
    ).first()

    if not user_report:
        raise HTTPException(status_code=404, detail="User report association not found")

    user_report.custom_name = data.custom_name
    user_report.updated_at = datetime.now()

    db.add(user_report)
    db.commit()
    db.refresh(user_report)

    return UserReportResponse(
        id=user_report.id,
        user_id=user_report.user_id,
        report_id=user_report.report_id,
        custom_name=user_report.custom_name,
        is_creator=user_report.is_creator,
        created_at=user_report.created_at.isoformat(),
        updated_at=user_report.updated_at.isoformat(),
    )


@router.delete("/{user_id}/reports/{report_id}")
async def delete_user_report(
    user_id: str,
    report_id: str,
    db: Session = Depends(get_session),
):
    """Delete a user-report association."""
    user_report = db.exec(
        select(UserReportTable)
        .where(UserReportTable.user_id == user_id)
        .where(UserReportTable.report_id == report_id)
    ).first()

    if not user_report:
        raise HTTPException(status_code=404, detail="User report association not found")

    db.delete(user_report)
    db.commit()

    return {"message": "User report association deleted"}


class UserPolicyResponse(BaseModel):
    id: str
    user_id: str
    policy_id: str
    custom_name: str | None
    is_creator: bool
    created_at: str
    updated_at: str


class UserPolicyCreate(BaseModel):
    policy_id: str
    custom_name: str | None = None


class UserPolicyUpdate(BaseModel):
    custom_name: str


@router.get("/{user_id}/policies", response_model=List[UserPolicyResponse])
async def get_user_policies(
    user_id: str,
    db: Session = Depends(get_session),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=10_000),
):
    """Get all policy associations for a user."""
    user = db.get(UserTable, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    user_policies = db.exec(
        select(UserPolicyTable)
        .where(UserPolicyTable.user_id == user_id)
        .offset(skip)
        .limit(limit)
    ).all()

    return [
        UserPolicyResponse(
            id=up.id,
            user_id=up.user_id,
            policy_id=up.policy_id,
            custom_name=up.custom_name,
            is_creator=up.is_creator,
            created_at=up.created_at.isoformat(),
            updated_at=up.updated_at.isoformat(),
        )
        for up in user_policies
    ]


@router.post("/{user_id}/policies", response_model=UserPolicyResponse)
async def create_user_policy(
    user_id: str,
    data: UserPolicyCreate,
    db: Session = Depends(get_session),
):
    """Create a user-policy association (bookmark a policy)."""
    user = db.get(UserTable, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    policy = db.get(PolicyTable, data.policy_id)
    if not policy:
        raise HTTPException(status_code=404, detail="Policy not found")

    existing = db.exec(
        select(UserPolicyTable)
        .where(UserPolicyTable.user_id == user_id)
        .where(UserPolicyTable.policy_id == data.policy_id)
    ).first()

    if existing:
        raise HTTPException(
            status_code=400, detail="User already has association with this policy"
        )

    user_policy = UserPolicyTable(
        user_id=user_id,
        policy_id=data.policy_id,
        custom_name=data.custom_name,
        is_creator=False,
    )
    db.add(user_policy)
    db.commit()
    db.refresh(user_policy)

    return UserPolicyResponse(
        id=user_policy.id,
        user_id=user_policy.user_id,
        policy_id=user_policy.policy_id,
        custom_name=user_policy.custom_name,
        is_creator=user_policy.is_creator,
        created_at=user_policy.created_at.isoformat(),
        updated_at=user_policy.updated_at.isoformat(),
    )


@router.patch("/{user_id}/policies/{policy_id}", response_model=UserPolicyResponse)
async def update_user_policy(
    user_id: str,
    policy_id: str,
    data: UserPolicyUpdate,
    db: Session = Depends(get_session),
):
    """Update a user-policy association."""
    user_policy = db.exec(
        select(UserPolicyTable)
        .where(UserPolicyTable.user_id == user_id)
        .where(UserPolicyTable.policy_id == policy_id)
    ).first()

    if not user_policy:
        raise HTTPException(status_code=404, detail="User policy association not found")

    user_policy.custom_name = data.custom_name
    user_policy.updated_at = datetime.now()

    db.add(user_policy)
    db.commit()
    db.refresh(user_policy)

    return UserPolicyResponse(
        id=user_policy.id,
        user_id=user_policy.user_id,
        policy_id=user_policy.policy_id,
        custom_name=user_policy.custom_name,
        is_creator=user_policy.is_creator,
        created_at=user_policy.created_at.isoformat(),
        updated_at=user_policy.updated_at.isoformat(),
    )


@router.delete("/{user_id}/policies/{policy_id}")
async def delete_user_policy(
    user_id: str,
    policy_id: str,
    db: Session = Depends(get_session),
):
    """Delete a user-policy association."""
    user_policy = db.exec(
        select(UserPolicyTable)
        .where(UserPolicyTable.user_id == user_id)
        .where(UserPolicyTable.policy_id == policy_id)
    ).first()

    if not user_policy:
        raise HTTPException(status_code=404, detail="User policy association not found")

    db.delete(user_policy)
    db.commit()

    return {"message": "User policy association deleted"}


# Datasets models
class UserDatasetResponse(BaseModel):
    id: str
    user_id: str
    dataset_id: str
    custom_name: str | None
    is_creator: bool
    created_at: str
    updated_at: str


class UserDatasetCreate(BaseModel):
    dataset_id: str
    custom_name: str | None = None


class UserDatasetUpdate(BaseModel):
    custom_name: str


# Simulations models
class UserSimulationResponse(BaseModel):
    id: str
    user_id: str
    simulation_id: str
    custom_name: str | None
    is_creator: bool
    created_at: str
    updated_at: str


class UserSimulationCreate(BaseModel):
    simulation_id: str
    custom_name: str | None = None


class UserSimulationUpdate(BaseModel):
    custom_name: str


# Dynamics models
class UserDynamicResponse(BaseModel):
    id: str
    user_id: str
    dynamic_id: str
    custom_name: str | None
    is_creator: bool
    created_at: str
    updated_at: str


class UserDynamicCreate(BaseModel):
    dynamic_id: str
    custom_name: str | None = None


class UserDynamicUpdate(BaseModel):
    custom_name: str


@router.get("/{user_id}/datasets", response_model=List[UserDatasetResponse])
async def get_user_datasets(
    user_id: str,
    db: Session = Depends(get_session),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=10_000),
):
    """Get all dataset associations for a user."""
    user = db.get(UserTable, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    user_datasets = db.exec(
        select(UserDatasetTable)
        .where(UserDatasetTable.user_id == user_id)
        .offset(skip)
        .limit(limit)
    ).all()

    return [
        UserDatasetResponse(
            id=ud.id,
            user_id=ud.user_id,
            dataset_id=ud.dataset_id,
            custom_name=ud.custom_name,
            is_creator=ud.is_creator,
            created_at=ud.created_at.isoformat(),
            updated_at=ud.updated_at.isoformat(),
        )
        for ud in user_datasets
    ]


@router.get("/{user_id}/simulations", response_model=List[UserSimulationResponse])
async def get_user_simulations(
    user_id: str,
    db: Session = Depends(get_session),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=10_000),
):
    """Get all simulation associations for a user."""
    user = db.get(UserTable, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    user_simulations = db.exec(
        select(UserSimulationTable)
        .where(UserSimulationTable.user_id == user_id)
        .offset(skip)
        .limit(limit)
    ).all()

    return [
        UserSimulationResponse(
            id=us.id,
            user_id=us.user_id,
            simulation_id=us.simulation_id,
            custom_name=us.custom_name,
            is_creator=us.is_creator,
            created_at=us.created_at.isoformat(),
            updated_at=us.updated_at.isoformat(),
        )
        for us in user_simulations
    ]


@router.post("/{user_id}/datasets", response_model=UserDatasetResponse)
async def create_user_dataset(
    user_id: str,
    data: UserDatasetCreate,
    db: Session = Depends(get_session),
):
    """Create a user-dataset association."""
    user = db.get(UserTable, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    dataset = db.get(DatasetTable, data.dataset_id)
    if not dataset:
        raise HTTPException(status_code=404, detail="Dataset not found")

    existing = db.exec(
        select(UserDatasetTable)
        .where(UserDatasetTable.user_id == user_id)
        .where(UserDatasetTable.dataset_id == data.dataset_id)
    ).first()

    if existing:
        raise HTTPException(
            status_code=400, detail="User already has association with this dataset"
        )

    user_dataset = UserDatasetTable(
        user_id=user_id,
        dataset_id=data.dataset_id,
        custom_name=data.custom_name,
        is_creator=False,
    )
    db.add(user_dataset)
    db.commit()
    db.refresh(user_dataset)

    return UserDatasetResponse(
        id=user_dataset.id,
        user_id=user_dataset.user_id,
        dataset_id=user_dataset.dataset_id,
        custom_name=user_dataset.custom_name,
        is_creator=user_dataset.is_creator,
        created_at=user_dataset.created_at.isoformat(),
        updated_at=user_dataset.updated_at.isoformat(),
    )


@router.patch("/{user_id}/datasets/{dataset_id}", response_model=UserDatasetResponse)
async def update_user_dataset(
    user_id: str,
    dataset_id: str,
    data: UserDatasetUpdate,
    db: Session = Depends(get_session),
):
    """Update a user-dataset association."""
    user_dataset = db.exec(
        select(UserDatasetTable)
        .where(UserDatasetTable.user_id == user_id)
        .where(UserDatasetTable.dataset_id == dataset_id)
    ).first()

    if not user_dataset:
        raise HTTPException(status_code=404, detail="User dataset association not found")

    user_dataset.custom_name = data.custom_name
    user_dataset.updated_at = datetime.now()

    db.add(user_dataset)
    db.commit()
    db.refresh(user_dataset)

    return UserDatasetResponse(
        id=user_dataset.id,
        user_id=user_dataset.user_id,
        dataset_id=user_dataset.dataset_id,
        custom_name=user_dataset.custom_name,
        is_creator=user_dataset.is_creator,
        created_at=user_dataset.created_at.isoformat(),
        updated_at=user_dataset.updated_at.isoformat(),
    )


@router.delete("/{user_id}/datasets/{dataset_id}")
async def delete_user_dataset(
    user_id: str,
    dataset_id: str,
    db: Session = Depends(get_session),
):
    """Delete a user-dataset association."""
    user_dataset = db.exec(
        select(UserDatasetTable)
        .where(UserDatasetTable.user_id == user_id)
        .where(UserDatasetTable.dataset_id == dataset_id)
    ).first()

    if not user_dataset:
        raise HTTPException(status_code=404, detail="User dataset association not found")

    db.delete(user_dataset)
    db.commit()

    return {"message": "User dataset association deleted"}


@router.post("/{user_id}/simulations", response_model=UserSimulationResponse)
async def create_user_simulation(
    user_id: str,
    data: UserSimulationCreate,
    db: Session = Depends(get_session),
):
    """Create a user-simulation association."""
    user = db.get(UserTable, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    simulation = db.get(SimulationTable, data.simulation_id)
    if not simulation:
        raise HTTPException(status_code=404, detail="Simulation not found")

    existing = db.exec(
        select(UserSimulationTable)
        .where(UserSimulationTable.user_id == user_id)
        .where(UserSimulationTable.simulation_id == data.simulation_id)
    ).first()

    if existing:
        raise HTTPException(
            status_code=400, detail="User already has association with this simulation"
        )

    user_simulation = UserSimulationTable(
        user_id=user_id,
        simulation_id=data.simulation_id,
        custom_name=data.custom_name,
        is_creator=False,
    )
    db.add(user_simulation)
    db.commit()
    db.refresh(user_simulation)

    return UserSimulationResponse(
        id=user_simulation.id,
        user_id=user_simulation.user_id,
        simulation_id=user_simulation.simulation_id,
        custom_name=user_simulation.custom_name,
        is_creator=user_simulation.is_creator,
        created_at=user_simulation.created_at.isoformat(),
        updated_at=user_simulation.updated_at.isoformat(),
    )


@router.patch("/{user_id}/simulations/{simulation_id}", response_model=UserSimulationResponse)
async def update_user_simulation(
    user_id: str,
    simulation_id: str,
    data: UserSimulationUpdate,
    db: Session = Depends(get_session),
):
    """Update a user-simulation association."""
    user_simulation = db.exec(
        select(UserSimulationTable)
        .where(UserSimulationTable.user_id == user_id)
        .where(UserSimulationTable.simulation_id == simulation_id)
    ).first()

    if not user_simulation:
        raise HTTPException(status_code=404, detail="User simulation association not found")

    user_simulation.custom_name = data.custom_name
    user_simulation.updated_at = datetime.now()

    db.add(user_simulation)
    db.commit()
    db.refresh(user_simulation)

    return UserSimulationResponse(
        id=user_simulation.id,
        user_id=user_simulation.user_id,
        simulation_id=user_simulation.simulation_id,
        custom_name=user_simulation.custom_name,
        is_creator=user_simulation.is_creator,
        created_at=user_simulation.created_at.isoformat(),
        updated_at=user_simulation.updated_at.isoformat(),
    )


@router.delete("/{user_id}/simulations/{simulation_id}")
async def delete_user_simulation(
    user_id: str,
    simulation_id: str,
    db: Session = Depends(get_session),
):
    """Delete a user-simulation association."""
    user_simulation = db.exec(
        select(UserSimulationTable)
        .where(UserSimulationTable.user_id == user_id)
        .where(UserSimulationTable.simulation_id == simulation_id)
    ).first()

    if not user_simulation:
        raise HTTPException(status_code=404, detail="User simulation association not found")

    db.delete(user_simulation)
    db.commit()

    return {"message": "User simulation association deleted"}


@router.get("/{user_id}/dynamics", response_model=List[UserDynamicResponse])
async def get_user_dynamics(
    user_id: str,
    db: Session = Depends(get_session),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=10_000),
):
    """Get all dynamic associations for a user."""
    user = db.get(UserTable, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    user_dynamics = db.exec(
        select(UserDynamicTable)
        .where(UserDynamicTable.user_id == user_id)
        .offset(skip)
        .limit(limit)
    ).all()

    return [
        UserDynamicResponse(
            id=ud.id,
            user_id=ud.user_id,
            dynamic_id=ud.dynamic_id,
            custom_name=ud.custom_name,
            is_creator=ud.is_creator,
            created_at=ud.created_at.isoformat(),
            updated_at=ud.updated_at.isoformat(),
        )
        for ud in user_dynamics
    ]


@router.post("/{user_id}/dynamics", response_model=UserDynamicResponse)
async def create_user_dynamic(
    user_id: str,
    data: UserDynamicCreate,
    db: Session = Depends(get_session),
):
    """Create a user-dynamic association."""
    user = db.get(UserTable, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    dynamic = db.get(DynamicTable, data.dynamic_id)
    if not dynamic:
        raise HTTPException(status_code=404, detail="Dynamic not found")

    existing = db.exec(
        select(UserDynamicTable)
        .where(UserDynamicTable.user_id == user_id)
        .where(UserDynamicTable.dynamic_id == data.dynamic_id)
    ).first()

    if existing:
        raise HTTPException(
            status_code=400, detail="User already has association with this dynamic"
        )

    user_dynamic = UserDynamicTable(
        user_id=user_id,
        dynamic_id=data.dynamic_id,
        custom_name=data.custom_name,
        is_creator=False,
    )
    db.add(user_dynamic)
    db.commit()
    db.refresh(user_dynamic)

    return UserDynamicResponse(
        id=user_dynamic.id,
        user_id=user_dynamic.user_id,
        dynamic_id=user_dynamic.dynamic_id,
        custom_name=user_dynamic.custom_name,
        is_creator=user_dynamic.is_creator,
        created_at=user_dynamic.created_at.isoformat(),
        updated_at=user_dynamic.updated_at.isoformat(),
    )


@router.patch("/{user_id}/dynamics/{dynamic_id}", response_model=UserDynamicResponse)
async def update_user_dynamic(
    user_id: str,
    dynamic_id: str,
    data: UserDynamicUpdate,
    db: Session = Depends(get_session),
):
    """Update a user-dynamic association."""
    user_dynamic = db.exec(
        select(UserDynamicTable)
        .where(UserDynamicTable.user_id == user_id)
        .where(UserDynamicTable.dynamic_id == dynamic_id)
    ).first()

    if not user_dynamic:
        raise HTTPException(status_code=404, detail="User dynamic association not found")

    user_dynamic.custom_name = data.custom_name
    user_dynamic.updated_at = datetime.now()

    db.add(user_dynamic)
    db.commit()
    db.refresh(user_dynamic)

    return UserDynamicResponse(
        id=user_dynamic.id,
        user_id=user_dynamic.user_id,
        dynamic_id=user_dynamic.dynamic_id,
        custom_name=user_dynamic.custom_name,
        is_creator=user_dynamic.is_creator,
        created_at=user_dynamic.created_at.isoformat(),
        updated_at=user_dynamic.updated_at.isoformat(),
    )


@router.delete("/{user_id}/dynamics/{dynamic_id}")
async def delete_user_dynamic(
    user_id: str,
    dynamic_id: str,
    db: Session = Depends(get_session),
):
    """Delete a user-dynamic association."""
    user_dynamic = db.exec(
        select(UserDynamicTable)
        .where(UserDynamicTable.user_id == user_id)
        .where(UserDynamicTable.dynamic_id == dynamic_id)
    ).first()

    if not user_dynamic:
        raise HTTPException(status_code=404, detail="User dynamic association not found")

    db.delete(user_dynamic)
    db.commit()

    return {"message": "User dynamic association deleted"}
