from fastapi import APIRouter, HTTPException, Depends, Query
from sqlmodel import Session, select
from policyengine.database import AggregateChangeTable
from policyengine_api_full.database import database
from policyengine.models import AggregateChange
from policyengine_api_full.database import get_session
from typing import Optional
from datetime import datetime, timezone
from pydantic import BaseModel

aggregate_changes_router = APIRouter(prefix="/aggregate-changes", tags=["aggregate_changes"])


class AggregateChangeUpdateRequest(BaseModel):
    """Request model for updating an aggregate change."""
    baseline_value: Optional[float] = None
    comparison_value: Optional[float] = None
    change: Optional[float] = None
    relative_change: Optional[float] = None


@aggregate_changes_router.get("/", response_model=list[AggregateChangeTable])
def list_aggregate_changes(
    session: Session = Depends(get_session),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=10_000),
    baseline_simulation_id: Optional[str] = Query(None, description="Filter by baseline simulation ID"),
    comparison_simulation_id: Optional[str] = Query(None, description="Filter by comparison simulation ID"),
    reportelement_id: Optional[str] = Query(None, description="Filter by report element ID"),
    entity: Optional[str] = Query(None, description="Filter by entity"),
    variable_name: Optional[str] = Query(None, description="Filter by variable name"),
):
    """List all aggregate changes with pagination and optional filters."""
    statement = select(AggregateChangeTable)

    if baseline_simulation_id:
        statement = statement.where(AggregateChangeTable.baseline_simulation_id == baseline_simulation_id)
    if comparison_simulation_id:
        statement = statement.where(AggregateChangeTable.comparison_simulation_id == comparison_simulation_id)
    if reportelement_id:
        statement = statement.where(AggregateChangeTable.reportelement_id == reportelement_id)
    if entity:
        statement = statement.where(AggregateChangeTable.entity == entity)
    if variable_name:
        statement = statement.where(AggregateChangeTable.variable_name == variable_name)

    statement = statement.offset(skip).limit(limit)
    aggregate_changes = session.exec(statement).all()
    return aggregate_changes


@aggregate_changes_router.post("/", response_model=AggregateChangeTable, status_code=201)
def create_aggregate_change(
    aggregate_change: AggregateChangeTable,
    session: Session = Depends(get_session),
):
    """Create a new aggregate change (typically with pre-computed values)."""
    if not aggregate_change.id:
        import uuid
        aggregate_change.id = str(uuid.uuid4())

    session.add(aggregate_change)
    session.commit()
    session.refresh(aggregate_change)
    return aggregate_change


@aggregate_changes_router.get("/{aggregate_change_id}", response_model=AggregateChangeTable)
def get_aggregate_change(
    aggregate_change_id: str,
    session: Session = Depends(get_session),
):
    """Get a single aggregate change by ID."""
    aggregate_change = session.get(AggregateChangeTable, aggregate_change_id)
    if not aggregate_change:
        raise HTTPException(status_code=404, detail="Aggregate change not found")
    return aggregate_change


@aggregate_changes_router.patch("/{aggregate_change_id}", response_model=AggregateChangeTable)
def update_aggregate_change(
    aggregate_change_id: str,
    update_request: AggregateChangeUpdateRequest,
    session: Session = Depends(get_session),
):
    """Update an aggregate change's values."""
    db_aggregate_change = session.get(AggregateChangeTable, aggregate_change_id)
    if not db_aggregate_change:
        raise HTTPException(status_code=404, detail="Aggregate change not found")

    if update_request.baseline_value is not None:
        db_aggregate_change.baseline_value = update_request.baseline_value
    if update_request.comparison_value is not None:
        db_aggregate_change.comparison_value = update_request.comparison_value
    if update_request.change is not None:
        db_aggregate_change.change = update_request.change
    if update_request.relative_change is not None:
        db_aggregate_change.relative_change = update_request.relative_change

    session.add(db_aggregate_change)
    session.commit()
    session.refresh(db_aggregate_change)
    return db_aggregate_change


@aggregate_changes_router.delete("/{aggregate_change_id}", status_code=204)
def delete_aggregate_change(
    aggregate_change_id: str,
    session: Session = Depends(get_session),
):
    """Delete an aggregate change."""
    aggregate_change = session.get(AggregateChangeTable, aggregate_change_id)
    if not aggregate_change:
        raise HTTPException(status_code=404, detail="Aggregate change not found")

    session.delete(aggregate_change)
    session.commit()
    return None


@aggregate_changes_router.post("/bulk", response_model=list[AggregateChangeTable], status_code=201)
def create_bulk_aggregate_changes(
    aggregate_changes: list[AggregateChangeTable],
    session: Session = Depends(get_session),
):
    """Create multiple aggregate changes at once and queue them for processing."""
    import uuid

    created_aggregate_changes = []
    for aggregate_change in aggregate_changes:
        if not aggregate_change.id:
            aggregate_change.id = str(uuid.uuid4())
        # Don't set values - leave as None to indicate pending processing
        aggregate_change.baseline_value = None
        aggregate_change.comparison_value = None
        aggregate_change.change = None
        aggregate_change.relative_change = None
        created_aggregate_changes.append(aggregate_change)

    # Save to database without computing (will be picked up by queue worker)
    for aggregate_change in created_aggregate_changes:
        session.add(aggregate_change)

    session.commit()

    # Refresh all aggregate changes
    for aggregate_change in created_aggregate_changes:
        session.refresh(aggregate_change)

    return created_aggregate_changes


@aggregate_changes_router.get("/by-report-element/{reportelement_id}", response_model=list[AggregateChangeTable])
def get_aggregate_changes_by_report_element(
    reportelement_id: str,
    session: Session = Depends(get_session),
):
    """Get all aggregate changes for a specific report element."""
    statement = select(AggregateChangeTable).where(
        AggregateChangeTable.reportelement_id == reportelement_id
    )
    aggregate_changes = session.exec(statement).all()
    return aggregate_changes