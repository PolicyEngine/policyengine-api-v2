from fastapi import APIRouter, HTTPException, Depends, Query
from sqlmodel import Session, select
from policyengine.database import ModelVersionTable
from policyengine_api_full.database import get_session
from typing import Optional

router = APIRouter(prefix="/model-versions", tags=["model versions"])


@router.get("/", response_model=list[ModelVersionTable])
def list_model_versions(
    session: Session = Depends(get_session),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    model_id: Optional[str] = Query(None, description="Filter by model ID"),
):
    """List all model versions with pagination and optional filters."""
    statement = select(ModelVersionTable)

    if model_id:
        statement = statement.where(ModelVersionTable.model_id == model_id)

    statement = statement.offset(skip).limit(limit)
    model_versions = session.exec(statement).all()
    return model_versions


@router.post("/", response_model=ModelVersionTable, status_code=201)
def create_model_version(
    model_version: ModelVersionTable,
    session: Session = Depends(get_session),
):
    """Create a new model version."""
    session.add(model_version)
    session.commit()
    session.refresh(model_version)
    return model_version


@router.get("/{model_version_id}", response_model=ModelVersionTable)
def get_model_version(
    model_version_id: str,
    session: Session = Depends(get_session),
):
    """Get a single model version by ID."""
    model_version = session.get(ModelVersionTable, model_version_id)
    if not model_version:
        raise HTTPException(status_code=404, detail="Model version not found")
    return model_version


@router.patch("/{model_version_id}", response_model=ModelVersionTable)
def update_model_version(
    model_version_id: str,
    version_name: Optional[str] = None,
    session: Session = Depends(get_session),
):
    """Update a model version."""
    db_model_version = session.get(ModelVersionTable, model_version_id)
    if not db_model_version:
        raise HTTPException(status_code=404, detail="Model version not found")

    if version_name is not None:
        db_model_version.version_name = version_name

    session.add(db_model_version)
    session.commit()
    session.refresh(db_model_version)
    return db_model_version


@router.delete("/{model_version_id}", status_code=204)
def delete_model_version(
    model_version_id: str,
    session: Session = Depends(get_session),
):
    """Delete a model version."""
    model_version = session.get(ModelVersionTable, model_version_id)
    if not model_version:
        raise HTTPException(status_code=404, detail="Model version not found")

    session.delete(model_version)
    session.commit()
    return None