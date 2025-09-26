from fastapi import APIRouter, HTTPException, Depends, Query
from sqlmodel import Session, select
from policyengine.database import PolicyTable
from policyengine_api_full.database import get_session
from policyengine_api_full.schemas import PolicyResponse, PolicyCreate, PolicyUpdate, decode_bytes
from typing import Optional
from datetime import datetime
from uuid import uuid4

router = APIRouter(prefix="/policies", tags=["policies"])


@router.get("/", response_model=list[PolicyResponse])
def list_policies(
    session: Session = Depends(get_session),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
):
    """List all policies with pagination."""
    statement = select(PolicyTable).offset(skip).limit(limit)
    policies = session.exec(statement).all()
    return [PolicyResponse.from_orm(p) for p in policies]


@router.post("/", response_model=PolicyResponse, status_code=201)
def create_policy(
    policy: PolicyCreate,
    session: Session = Depends(get_session),
):
    """Create a new policy."""
    db_policy = PolicyTable(
        id=str(uuid4()),
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
        **policy.to_orm_dict()
    )
    session.add(db_policy)
    session.commit()
    session.refresh(db_policy)
    return PolicyResponse.from_orm(db_policy)


@router.get("/{policy_id}", response_model=PolicyResponse)
def get_policy(
    policy_id: str,
    session: Session = Depends(get_session),
):
    """Get a single policy by ID."""
    policy = session.get(PolicyTable, policy_id)
    if not policy:
        raise HTTPException(status_code=404, detail="Policy not found")
    return PolicyResponse.from_orm(policy)


@router.patch("/{policy_id}", response_model=PolicyResponse)
def update_policy(
    policy_id: str,
    update: PolicyUpdate,
    session: Session = Depends(get_session),
):
    """Update a policy."""
    db_policy = session.get(PolicyTable, policy_id)
    if not db_policy:
        raise HTTPException(status_code=404, detail="Policy not found")

    if update.name is not None:
        db_policy.name = update.name
    if update.description is not None:
        db_policy.description = update.description
    if update.simulation_modifier is not None:
        db_policy.simulation_modifier = decode_bytes(update.simulation_modifier)

    db_policy.updated_at = datetime.utcnow()

    session.add(db_policy)
    session.commit()
    session.refresh(db_policy)
    return PolicyResponse.from_orm(db_policy)


@router.delete("/{policy_id}", status_code=204)
def delete_policy(
    policy_id: str,
    session: Session = Depends(get_session),
):
    """Delete a policy."""
    policy = session.get(PolicyTable, policy_id)
    if not policy:
        raise HTTPException(status_code=404, detail="Policy not found")

    session.delete(policy)
    session.commit()
    return None