from fastapi import APIRouter, HTTPException, Depends, Query
from sqlmodel import Session, select
from policyengine.database import BaselineVariableTable
from policyengine_api_full.database import get_session
from typing import Optional

router = APIRouter(prefix="/baseline-variables", tags=["baseline variables"])


@router.get("/", response_model=list[BaselineVariableTable])
def list_baseline_variables(
    session: Session = Depends(get_session),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    variable_name: Optional[str] = Query(None, description="Filter by variable name"),
    model_id: Optional[str] = Query(None, description="Filter by model ID"),
):
    """List all baseline variables with pagination and optional filters."""
    statement = select(BaselineVariableTable)

    if variable_name:
        statement = statement.where(BaselineVariableTable.variable_name == variable_name)
    if model_id:
        statement = statement.where(BaselineVariableTable.model_id == model_id)

    statement = statement.offset(skip).limit(limit)
    baseline_variables = session.exec(statement).all()
    return baseline_variables


@router.post("/", response_model=BaselineVariableTable, status_code=201)
def create_baseline_variable(
    baseline_variable: BaselineVariableTable,
    session: Session = Depends(get_session),
):
    """Create a new baseline variable."""
    session.add(baseline_variable)
    session.commit()
    session.refresh(baseline_variable)
    return baseline_variable


@router.get("/{baseline_variable_id}", response_model=BaselineVariableTable)
def get_baseline_variable(
    baseline_variable_id: str,
    session: Session = Depends(get_session),
):
    """Get a single baseline variable by ID."""
    baseline_variable = session.get(BaselineVariableTable, baseline_variable_id)
    if not baseline_variable:
        raise HTTPException(status_code=404, detail="Baseline variable not found")
    return baseline_variable


@router.patch("/{baseline_variable_id}", response_model=BaselineVariableTable)
def update_baseline_variable(
    baseline_variable_id: str,
    variable_name: Optional[str] = None,
    value: Optional[bytes] = None,
    session: Session = Depends(get_session),
):
    """Update a baseline variable."""
    db_baseline_variable = session.get(BaselineVariableTable, baseline_variable_id)
    if not db_baseline_variable:
        raise HTTPException(status_code=404, detail="Baseline variable not found")

    if variable_name is not None:
        db_baseline_variable.variable_name = variable_name
    if value is not None:
        db_baseline_variable.value = value

    session.add(db_baseline_variable)
    session.commit()
    session.refresh(db_baseline_variable)
    return db_baseline_variable


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