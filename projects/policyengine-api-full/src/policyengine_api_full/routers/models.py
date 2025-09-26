from fastapi import APIRouter, HTTPException, Depends, Query
from sqlmodel import Session, select
from policyengine.database import ModelTable
from policyengine_api_full.database import get_session
from policyengine_api_full.schemas import ModelResponse, ModelCreate, ModelUpdate, decode_bytes
from typing import Optional

router = APIRouter(prefix="/models", tags=["models"])


@router.get("/", response_model=list[ModelResponse])
def list_models(
    session: Session = Depends(get_session),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
):
    """List all models with pagination."""
    statement = select(ModelTable).offset(skip).limit(limit)
    models = session.exec(statement).all()
    return [ModelResponse.from_orm(m) for m in models]


@router.post("/", response_model=ModelResponse, status_code=201)
def create_model(
    model: ModelCreate,
    session: Session = Depends(get_session),
):
    """Create a new model."""
    db_model = ModelTable(**model.to_orm_dict())
    session.add(db_model)
    session.commit()
    session.refresh(db_model)
    return ModelResponse.from_orm(db_model)


@router.get("/{model_id}", response_model=ModelResponse)
def get_model(
    model_id: str,
    session: Session = Depends(get_session),
):
    """Get a single model by ID."""
    model = session.get(ModelTable, model_id)
    if not model:
        raise HTTPException(status_code=404, detail="Model not found")
    return ModelResponse.from_orm(model)


@router.patch("/{model_id}", response_model=ModelResponse)
def update_model(
    model_id: str,
    update: ModelUpdate,
    session: Session = Depends(get_session),
):
    """Update a model."""
    db_model = session.get(ModelTable, model_id)
    if not db_model:
        raise HTTPException(status_code=404, detail="Model not found")

    if update.name is not None:
        db_model.name = update.name
    if update.description is not None:
        db_model.description = update.description
    if update.simulation_function is not None:
        db_model.simulation_function = decode_bytes(update.simulation_function)

    session.add(db_model)
    session.commit()
    session.refresh(db_model)
    return ModelResponse.from_orm(db_model)


@router.delete("/{model_id}", status_code=204)
def delete_model(
    model_id: str,
    session: Session = Depends(get_session),
):
    """Delete a model."""
    model = session.get(ModelTable, model_id)
    if not model:
        raise HTTPException(status_code=404, detail="Model not found")

    session.delete(model)
    session.commit()
    return None