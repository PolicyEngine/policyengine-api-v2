"""User policy management endpoints."""
from fastapi import APIRouter, HTTPException, Depends
from sqlmodel import Session, select
from typing import List
from pydantic import BaseModel
from policyengine_api_full.models import UserPolicyTable
from policyengine_api_full.database import get_session

router = APIRouter(prefix="/user-policies", tags=["user policies"])


class UserPolicyCreate(BaseModel):
    user_id: str
    policy_id: str
    custom_name: str | None = None


class UserPolicyUpdate(BaseModel):
    custom_name: str


class UserPolicyResponse(BaseModel):
    id: str
    user_id: str
    policy_id: str
    custom_name: str | None
    created_at: str
    updated_at: str


@router.post("", response_model=UserPolicyResponse)
async def create_user_policy(
    data: UserPolicyCreate,
    db: Session = Depends(get_session)
):
    """Create a user policy link."""
    user_pol = UserPolicyTable(
        user_id=data.user_id,
        policy_id=data.policy_id,
        custom_name=data.custom_name,
    )
    db.add(user_pol)
    db.commit()
    db.refresh(user_pol)

    return UserPolicyResponse(
        id=user_pol.id,
        user_id=user_pol.user_id,
        policy_id=user_pol.policy_id,
        custom_name=user_pol.custom_name,
        created_at=user_pol.created_at.isoformat(),
        updated_at=user_pol.updated_at.isoformat(),
    )


@router.get("", response_model=List[UserPolicyResponse])
async def list_user_policies(
    user_id: str,
    db: Session = Depends(get_session)
):
    """List all policies for a user."""
    user_pols = db.exec(
        select(UserPolicyTable).where(UserPolicyTable.user_id == user_id)
    ).all()

    return [
        UserPolicyResponse(
            id=up.id,
            user_id=up.user_id,
            policy_id=up.policy_id,
            custom_name=up.custom_name,
            created_at=up.created_at.isoformat(),
            updated_at=up.updated_at.isoformat(),
        )
        for up in user_pols
    ]


@router.patch("/{user_pol_id}", response_model=UserPolicyResponse)
async def update_user_policy(
    user_pol_id: str,
    data: UserPolicyUpdate,
    db: Session = Depends(get_session)
):
    """Update a user policy's custom name."""
    user_pol = db.get(UserPolicyTable, user_pol_id)
    if not user_pol:
        raise HTTPException(status_code=404, detail="User policy not found")

    user_pol.custom_name = data.custom_name
    db.add(user_pol)
    db.commit()
    db.refresh(user_pol)

    return UserPolicyResponse(
        id=user_pol.id,
        user_id=user_pol.user_id,
        policy_id=user_pol.policy_id,
        custom_name=user_pol.custom_name,
        created_at=user_pol.created_at.isoformat(),
        updated_at=user_pol.updated_at.isoformat(),
    )


@router.delete("/{user_pol_id}")
async def delete_user_policy(
    user_pol_id: str,
    db: Session = Depends(get_session)
):
    """Delete a user policy link."""
    user_pol = db.get(UserPolicyTable, user_pol_id)
    if not user_pol:
        raise HTTPException(status_code=404, detail="User policy not found")

    db.delete(user_pol)
    db.commit()

    return {"message": "User policy deleted"}