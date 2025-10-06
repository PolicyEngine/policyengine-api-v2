from fastapi import APIRouter, HTTPException, Depends, Query
from sqlmodel import Session, select
from policyengine.database import DatasetTable, VersionedDatasetTable
from policyengine_api_full.database import get_session
from policyengine_api_full.schemas import (
    DatasetResponse, DatasetCreate, DatasetDetailResponse,
    VersionedDatasetResponse, VersionedDatasetCreate
)
from typing import Optional
from datetime import datetime
from uuid import uuid4

datasets_router = APIRouter(prefix="/datasets", tags=["datasets"])
versioned_datasets_router = APIRouter(prefix="/versioned-datasets", tags=["versioned datasets"])


# Dataset endpoints
@datasets_router.get("/", response_model=list[DatasetResponse])
def list_datasets(
    session: Session = Depends(get_session),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
):
    """List all datasets with pagination."""
    statement = select(DatasetTable).offset(skip).limit(limit)
    datasets = session.exec(statement).all()
    return [DatasetResponse.from_orm(d) for d in datasets]


@datasets_router.post("/", response_model=DatasetResponse, status_code=201)
def create_dataset(
    dataset: DatasetCreate,
    session: Session = Depends(get_session),
    user_id: Optional[str] = Query(None, description="User ID to automatically associate with this dataset"),
):
    """Create a new dataset. Optionally associate with a user by passing user_id query param."""
    from policyengine_api_full.models import UserDatasetTable

    db_dataset = DatasetTable(**dataset.to_orm_dict())
    session.add(db_dataset)
    session.commit()
    session.refresh(db_dataset)

    # Auto-create user association if user_id provided
    if user_id:
        user_dataset = UserDatasetTable(
            user_id=user_id,
            dataset_id=db_dataset.id,
            is_creator=True,
        )
        session.add(user_dataset)
        session.commit()

    return DatasetResponse.from_orm(db_dataset)


@datasets_router.get("/{dataset_id}", response_model=DatasetResponse)
def get_dataset(
    dataset_id: str,
    session: Session = Depends(get_session),
):
    """Get a single dataset by ID (without data field)."""
    dataset = session.get(DatasetTable, dataset_id)
    if not dataset:
        raise HTTPException(status_code=404, detail="Dataset not found")
    return DatasetResponse.from_orm(dataset)


@datasets_router.get("/{dataset_id}/detail", response_model=DatasetDetailResponse)
def get_dataset_detail(
    dataset_id: str,
    session: Session = Depends(get_session),
):
    """Get a single dataset by ID with full data."""
    dataset = session.get(DatasetTable, dataset_id)
    if not dataset:
        raise HTTPException(status_code=404, detail="Dataset not found")
    return DatasetDetailResponse.from_orm(dataset)


@datasets_router.patch("/{dataset_id}", response_model=DatasetResponse)
def update_dataset(
    dataset_id: str,
    name: Optional[str] = None,
    description: Optional[str] = None,
    session: Session = Depends(get_session),
):
    """Update a dataset."""
    db_dataset = session.get(DatasetTable, dataset_id)
    if not db_dataset:
        raise HTTPException(status_code=404, detail="Dataset not found")

    if name is not None:
        db_dataset.name = name
    if description is not None:
        db_dataset.description = description

    session.add(db_dataset)
    session.commit()
    session.refresh(db_dataset)
    return DatasetResponse.from_orm(db_dataset)


@datasets_router.delete("/{dataset_id}", status_code=204)
def delete_dataset(
    dataset_id: str,
    session: Session = Depends(get_session),
):
    """Delete a dataset."""
    dataset = session.get(DatasetTable, dataset_id)
    if not dataset:
        raise HTTPException(status_code=404, detail="Dataset not found")

    session.delete(dataset)
    session.commit()
    return None


# Versioned Dataset endpoints
@versioned_datasets_router.get("/", response_model=list[VersionedDatasetResponse])
def list_versioned_datasets(
    session: Session = Depends(get_session),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    dataset_id: Optional[str] = Query(None, description="Filter by dataset ID"),
):
    """List all versioned datasets with pagination and optional filters."""
    statement = select(VersionedDatasetTable)

    if dataset_id:
        statement = statement.where(VersionedDatasetTable.dataset_id == dataset_id)

    statement = statement.offset(skip).limit(limit)
    versioned_datasets = session.exec(statement).all()
    return [VersionedDatasetResponse.from_orm(v) for v in versioned_datasets]


@versioned_datasets_router.post("/", response_model=VersionedDatasetResponse, status_code=201)
def create_versioned_dataset(
    versioned_dataset: VersionedDatasetCreate,
    session: Session = Depends(get_session),
):
    """Create a new versioned dataset."""
    db_versioned = VersionedDatasetTable(
        id=str(uuid4()),
        **versioned_dataset.to_orm_dict()
    )
    session.add(db_versioned)
    session.commit()
    session.refresh(db_versioned)
    return VersionedDatasetResponse.from_orm(db_versioned)


@versioned_datasets_router.get("/{versioned_dataset_id}", response_model=VersionedDatasetResponse)
def get_versioned_dataset(
    versioned_dataset_id: str,
    session: Session = Depends(get_session),
):
    """Get a single versioned dataset by ID."""
    versioned_dataset = session.get(VersionedDatasetTable, versioned_dataset_id)
    if not versioned_dataset:
        raise HTTPException(status_code=404, detail="Versioned dataset not found")
    return VersionedDatasetResponse.from_orm(versioned_dataset)


@versioned_datasets_router.delete("/{versioned_dataset_id}", status_code=204)
def delete_versioned_dataset(
    versioned_dataset_id: str,
    session: Session = Depends(get_session),
):
    """Delete a versioned dataset."""
    versioned_dataset = session.get(VersionedDatasetTable, versioned_dataset_id)
    if not versioned_dataset:
        raise HTTPException(status_code=404, detail="Versioned dataset not found")

    session.delete(versioned_dataset)
    session.commit()
    return None