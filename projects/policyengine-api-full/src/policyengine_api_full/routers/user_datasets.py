"""User dataset management endpoints."""
from fastapi import APIRouter, HTTPException, Depends
from sqlmodel import Session, select
from typing import List
from pydantic import BaseModel
from policyengine_api_full.models import UserDatasetTable
from policyengine_api_full.database import get_session

router = APIRouter(prefix="/user-datasets", tags=["user datasets"])


class UserDatasetCreate(BaseModel):
    user_id: str
    dataset_id: str
    custom_name: str | None = None


class UserDatasetUpdate(BaseModel):
    custom_name: str


class UserDatasetResponse(BaseModel):
    id: str
    user_id: str
    dataset_id: str
    custom_name: str | None
    is_creator: bool
    created_at: str
    updated_at: str


@router.post("", response_model=UserDatasetResponse)
async def create_user_dataset(
    data: UserDatasetCreate,
    db: Session = Depends(get_session)
):
    """Create a user dataset link."""
    user_dataset = UserDatasetTable(
        user_id=data.user_id,
        dataset_id=data.dataset_id,
        custom_name=data.custom_name,
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


@router.get("", response_model=List[UserDatasetResponse])
async def list_user_datasets(
    user_id: str | None = None,
    db: Session = Depends(get_session)
):
    """List all datasets for a user."""
    if user_id:
        user_datasets = db.exec(
            select(UserDatasetTable).where(UserDatasetTable.user_id == user_id)
        ).all()
    else:
        user_datasets = db.exec(select(UserDatasetTable)).all()

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


@router.get("/{user_dataset_id}", response_model=UserDatasetResponse)
async def get_user_dataset(
    user_dataset_id: str,
    db: Session = Depends(get_session)
):
    """Get a specific user dataset."""
    user_dataset = db.get(UserDatasetTable, user_dataset_id)
    if not user_dataset:
        raise HTTPException(status_code=404, detail="User dataset not found")

    return UserDatasetResponse(
        id=user_dataset.id,
        user_id=user_dataset.user_id,
        dataset_id=user_dataset.dataset_id,
        custom_name=user_dataset.custom_name,
        is_creator=user_dataset.is_creator,
        created_at=user_dataset.created_at.isoformat(),
        updated_at=user_dataset.updated_at.isoformat(),
    )


@router.patch("/{user_dataset_id}", response_model=UserDatasetResponse)
async def update_user_dataset(
    user_dataset_id: str,
    data: UserDatasetUpdate,
    db: Session = Depends(get_session)
):
    """Update a user dataset's custom name."""
    user_dataset = db.get(UserDatasetTable, user_dataset_id)
    if not user_dataset:
        raise HTTPException(status_code=404, detail="User dataset not found")

    user_dataset.custom_name = data.custom_name
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


@router.delete("/{user_dataset_id}")
async def delete_user_dataset(
    user_dataset_id: str,
    db: Session = Depends(get_session)
):
    """Delete a user dataset link."""
    user_dataset = db.get(UserDatasetTable, user_dataset_id)
    if not user_dataset:
        raise HTTPException(status_code=404, detail="User dataset not found")

    db.delete(user_dataset)
    db.commit()

    return {"message": "User dataset deleted"}
