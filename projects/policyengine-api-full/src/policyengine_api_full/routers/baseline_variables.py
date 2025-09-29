from fastapi import APIRouter, HTTPException, Depends, Query
from sqlmodel import Session, select
from policyengine.database import BaselineVariableTable
from policyengine_api_full.database import get_session
from typing import Optional, List
from pydantic import BaseModel

router = APIRouter(prefix="/baseline-variables", tags=["baseline variables"])


class BaselineVariableResponse(BaseModel):
    """Response model for baseline variable."""
    id: str
    label: str
    description: Optional[str] = None
    entity: Optional[str] = None
    model_id: str
    model_version_id: Optional[str] = None


class BaselineVariableCreateRequest(BaseModel):
    """Request model for creating a baseline variable."""
    label: str
    model_id: str
    description: Optional[str] = None
    entity: Optional[str] = None
    model_version_id: Optional[str] = None


class BaselineVariableUpdateRequest(BaseModel):
    """Request model for updating a baseline variable."""
    label: Optional[str] = None
    description: Optional[str] = None
    entity: Optional[str] = None


@router.get("/", response_model=List[BaselineVariableResponse])
def list_baseline_variables(
    session: Session = Depends(get_session),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    label: Optional[str] = Query(None, description="Filter by label"),
    model_id: Optional[str] = Query(None, description="Filter by model ID"),
):
    """List all baseline variables with pagination and optional filters."""
    statement = select(BaselineVariableTable)

    if label:
        statement = statement.where(BaselineVariableTable.label == label)
    if model_id:
        statement = statement.where(BaselineVariableTable.model_id == model_id)

    statement = statement.offset(skip).limit(limit)
    baseline_variables = session.exec(statement).all()
    return [
        BaselineVariableResponse(
            id=bv.id,
            label=bv.label,
            description=bv.description,
            entity=bv.entity,
            model_id=bv.model_id,
            model_version_id=bv.model_version_id
        )
        for bv in baseline_variables
    ]


@router.post("/", response_model=BaselineVariableResponse, status_code=201)
def create_baseline_variable(
    request: BaselineVariableCreateRequest,
    session: Session = Depends(get_session),
):
    """Create a new baseline variable."""
    import uuid

    baseline_variable = BaselineVariableTable(
        id=str(uuid.uuid4()),
        label=request.label,
        description=request.description,
        entity=request.entity,
        model_id=request.model_id,
        model_version_id=request.model_version_id
    )

    session.add(baseline_variable)
    session.commit()
    session.refresh(baseline_variable)

    return BaselineVariableResponse(
        id=baseline_variable.id,
        label=baseline_variable.label,
        description=baseline_variable.description,
        entity=baseline_variable.entity,
        model_id=baseline_variable.model_id,
        model_version_id=baseline_variable.model_version_id
    )


@router.get("/{baseline_variable_id}", response_model=BaselineVariableResponse)
def get_baseline_variable(
    baseline_variable_id: str,
    session: Session = Depends(get_session),
):
    """Get a single baseline variable by ID."""
    baseline_variable = session.get(BaselineVariableTable, baseline_variable_id)
    if not baseline_variable:
        raise HTTPException(status_code=404, detail="Baseline variable not found")

    return BaselineVariableResponse(
        id=baseline_variable.id,
        label=baseline_variable.label,
        description=baseline_variable.description,
        entity=baseline_variable.entity,
        model_id=baseline_variable.model_id,
        model_version_id=baseline_variable.model_version_id
    )


@router.patch("/{baseline_variable_id}", response_model=BaselineVariableResponse)
def update_baseline_variable(
    baseline_variable_id: str,
    request: BaselineVariableUpdateRequest,
    session: Session = Depends(get_session),
):
    """Update a baseline variable."""
    db_baseline_variable = session.get(BaselineVariableTable, baseline_variable_id)
    if not db_baseline_variable:
        raise HTTPException(status_code=404, detail="Baseline variable not found")

    if request.label is not None:
        db_baseline_variable.label = request.label
    if request.description is not None:
        db_baseline_variable.description = request.description
    if request.entity is not None:
        db_baseline_variable.entity = request.entity

    session.add(db_baseline_variable)
    session.commit()
    session.refresh(db_baseline_variable)

    return BaselineVariableResponse(
        id=db_baseline_variable.id,
        label=db_baseline_variable.label,
        description=db_baseline_variable.description,
        entity=db_baseline_variable.entity,
        model_id=db_baseline_variable.model_id,
        model_version_id=db_baseline_variable.model_version_id
    )


@router.delete("/{baseline_variable_id}", status_code=204)
def delete_baseline_variable(
    baseline_variable_id: str,
    session: Session = Depends(get_session),
):
    """Delete a baseline variable."""
    baseline_variable = session.get(BaselineVariableTable, baseline_variable_id)
    if not baseline_variable:
        raise HTTPException(status_code=404, detail="Baseline variable not found")

    session.delete(baseline_variable)
    session.commit()
    return None