from fastapi import APIRouter, HTTPException, Depends, Query
from sqlmodel import Session, select
from policyengine.database import (
    ParameterTable,
    ParameterValueTable,
    BaselineParameterValueTable
)
from policyengine_api_full.database import get_session
from typing import Optional
from datetime import datetime, timezone

parameters_router = APIRouter(prefix="/parameters", tags=["parameters"])
parameter_values_router = APIRouter(prefix="/parameter-values", tags=["parameter values"])
baseline_parameter_values_router = APIRouter(prefix="/baseline-parameter-values", tags=["baseline parameter values"])


# Parameter endpoints
@parameters_router.get("/", response_model=list[ParameterTable])
def list_parameters(
    session: Session = Depends(get_session),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=10_000),
    model_id: Optional[str] = Query(None, description="Filter by model ID"),
):
    """List all parameters with pagination and optional filters."""
    statement = select(ParameterTable)

    if model_id:
        statement = statement.where(ParameterTable.model_id == model_id)

    statement = statement.offset(skip).limit(limit)
    parameters = session.exec(statement).all()
    return parameters


@parameters_router.post("/", response_model=ParameterTable, status_code=201)
def create_parameter(
    parameter: ParameterTable,
    session: Session = Depends(get_session),
):
    """Create a new parameter."""
    session.add(parameter)
    session.commit()
    session.refresh(parameter)
    return parameter


@parameters_router.get("/{parameter_id}/{model_id}", response_model=ParameterTable)
def get_parameter(
    parameter_id: str,
    model_id: str,
    session: Session = Depends(get_session),
):
    """Get a single parameter by ID and model ID (composite key)."""
    parameter = session.get(ParameterTable, (parameter_id, model_id))
    if not parameter:
        raise HTTPException(status_code=404, detail="Parameter not found")
    return parameter


@parameters_router.delete("/{parameter_id}/{model_id}", status_code=204)
def delete_parameter(
    parameter_id: str,
    model_id: str,
    session: Session = Depends(get_session),
):
    """Delete a parameter."""
    parameter = session.get(ParameterTable, (parameter_id, model_id))
    if not parameter:
        raise HTTPException(status_code=404, detail="Parameter not found")

    session.delete(parameter)
    session.commit()
    return None


# Parameter Value endpoints
@parameter_values_router.get("/", response_model=list[ParameterValueTable])
def list_parameter_values(
    session: Session = Depends(get_session),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=10_000),
    parameter_id: Optional[str] = Query(None, description="Filter by parameter ID"),
    policy_id: Optional[str] = Query(None, description="Filter by policy ID"),
):
    """List all parameter values with pagination and optional filters."""
    statement = select(ParameterValueTable)

    if parameter_id:
        statement = statement.where(ParameterValueTable.parameter_id == parameter_id)
    if policy_id:
        statement = statement.where(ParameterValueTable.policy_id == policy_id)

    statement = statement.offset(skip).limit(limit)
    parameter_values = session.exec(statement).all()
    return parameter_values


@parameter_values_router.post("/", response_model=ParameterValueTable, status_code=201)
def create_parameter_value(
    parameter_value: ParameterValueTable,
    session: Session = Depends(get_session),
):
    """Create a new parameter value."""
    session.add(parameter_value)
    session.commit()
    session.refresh(parameter_value)
    return parameter_value


@parameter_values_router.get("/{parameter_value_id}", response_model=ParameterValueTable)
def get_parameter_value(
    parameter_value_id: str,
    session: Session = Depends(get_session),
):
    """Get a single parameter value by ID."""
    parameter_value = session.get(ParameterValueTable, parameter_value_id)
    if not parameter_value:
        raise HTTPException(status_code=404, detail="Parameter value not found")
    return parameter_value


@parameter_values_router.patch("/{parameter_value_id}", response_model=ParameterValueTable)
def update_parameter_value(
    parameter_value_id: str,
    value: Optional[bytes] = None,
    session: Session = Depends(get_session),
):
    """Update a parameter value."""
    db_parameter_value = session.get(ParameterValueTable, parameter_value_id)
    if not db_parameter_value:
        raise HTTPException(status_code=404, detail="Parameter value not found")

    if value is not None:
        db_parameter_value.value = value

    db_parameter_value.updated_at = datetime.now(timezone.utc)

    session.add(db_parameter_value)
    session.commit()
    session.refresh(db_parameter_value)
    return db_parameter_value


@parameter_values_router.delete("/{parameter_value_id}", status_code=204)
def delete_parameter_value(
    parameter_value_id: str,
    session: Session = Depends(get_session),
):
    """Delete a parameter value."""
    parameter_value = session.get(ParameterValueTable, parameter_value_id)
    if not parameter_value:
        raise HTTPException(status_code=404, detail="Parameter value not found")

    session.delete(parameter_value)
    session.commit()
    return None


# Baseline Parameter Value endpoints
@baseline_parameter_values_router.get("/", response_model=list[BaselineParameterValueTable])
def list_baseline_parameter_values(
    session: Session = Depends(get_session),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=10_000),
    parameter_id: Optional[str] = Query(None, description="Filter by parameter ID"),
    model_id: Optional[str] = Query(None, description="Filter by model ID"),
):
    """List all baseline parameter values with pagination and optional filters."""
    statement = select(BaselineParameterValueTable)

    if parameter_id:
        statement = statement.where(BaselineParameterValueTable.parameter_id == parameter_id)
    if model_id:
        statement = statement.where(BaselineParameterValueTable.model_id == model_id)

    statement = statement.offset(skip).limit(limit)
    baseline_parameter_values = session.exec(statement).all()
    return baseline_parameter_values


@baseline_parameter_values_router.post("/", response_model=BaselineParameterValueTable, status_code=201)
def create_baseline_parameter_value(
    baseline_parameter_value: BaselineParameterValueTable,
    session: Session = Depends(get_session),
):
    """Create a new baseline parameter value."""
    session.add(baseline_parameter_value)
    session.commit()
    session.refresh(baseline_parameter_value)
    return baseline_parameter_value


@baseline_parameter_values_router.get("/{baseline_parameter_value_id}", response_model=BaselineParameterValueTable)
def get_baseline_parameter_value(
    baseline_parameter_value_id: str,
    session: Session = Depends(get_session),
):
    """Get a single baseline parameter value by ID."""
    baseline_parameter_value = session.get(BaselineParameterValueTable, baseline_parameter_value_id)
    if not baseline_parameter_value:
        raise HTTPException(status_code=404, detail="Baseline parameter value not found")
    return baseline_parameter_value


@baseline_parameter_values_router.delete("/{baseline_parameter_value_id}", status_code=204)
def delete_baseline_parameter_value(
    baseline_parameter_value_id: str,
    session: Session = Depends(get_session),
):
    """Delete a baseline parameter value."""
    baseline_parameter_value = session.get(BaselineParameterValueTable, baseline_parameter_value_id)
    if not baseline_parameter_value:
        raise HTTPException(status_code=404, detail="Baseline parameter value not found")

    session.delete(baseline_parameter_value)
    session.commit()
    return None