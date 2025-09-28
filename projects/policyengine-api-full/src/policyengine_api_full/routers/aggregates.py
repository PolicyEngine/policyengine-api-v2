from fastapi import APIRouter, HTTPException, Depends, Query
from sqlmodel import Session, select
from policyengine.database import AggregateTable
from policyengine_api_full.database import database
from policyengine.models import Aggregate
from policyengine_api_full.database import get_session
from typing import Optional
from datetime import datetime, timezone

aggregates_router = APIRouter(prefix="/aggregates", tags=["aggregates"])


@aggregates_router.get("/", response_model=list[AggregateTable])
def list_aggregates(
    session: Session = Depends(get_session),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=10_000),
    simulation_id: Optional[str] = Query(None, description="Filter by simulation ID"),
    reportelement_id: Optional[str] = Query(None, description="Filter by report element ID"),
    entity: Optional[str] = Query(None, description="Filter by entity"),
    variable_name: Optional[str] = Query(None, description="Filter by variable name"),
):
    """List all aggregates with pagination and optional filters."""
    statement = select(AggregateTable)

    if simulation_id:
        statement = statement.where(AggregateTable.simulation_id == simulation_id)
    if reportelement_id:
        statement = statement.where(AggregateTable.reportelement_id == reportelement_id)
    if entity:
        statement = statement.where(AggregateTable.entity == entity)
    if variable_name:
        statement = statement.where(AggregateTable.variable_name == variable_name)

    statement = statement.offset(skip).limit(limit)
    aggregates = session.exec(statement).all()
    return aggregates


@aggregates_router.post("/", response_model=AggregateTable, status_code=201)
def create_aggregate(
    aggregate: AggregateTable,
    session: Session = Depends(get_session),
):
    """Create a new aggregate (typically with a pre-computed value)."""
    if not aggregate.id:
        import uuid
        aggregate.id = str(uuid.uuid4())

    session.add(aggregate)
    session.commit()
    session.refresh(aggregate)
    return aggregate


@aggregates_router.get("/{aggregate_id}", response_model=AggregateTable)
def get_aggregate(
    aggregate_id: str,
    session: Session = Depends(get_session),
):
    """Get a single aggregate by ID."""
    aggregate = session.get(AggregateTable, aggregate_id)
    if not aggregate:
        raise HTTPException(status_code=404, detail="Aggregate not found")
    return aggregate


@aggregates_router.patch("/{aggregate_id}", response_model=AggregateTable)
def update_aggregate(
    aggregate_id: str,
    value: Optional[float] = None,
    session: Session = Depends(get_session),
):
    """Update an aggregate's value."""
    db_aggregate = session.get(AggregateTable, aggregate_id)
    if not db_aggregate:
        raise HTTPException(status_code=404, detail="Aggregate not found")

    if value is not None:
        db_aggregate.value = value

    session.add(db_aggregate)
    session.commit()
    session.refresh(db_aggregate)
    return db_aggregate


@aggregates_router.delete("/{aggregate_id}", status_code=204)
def delete_aggregate(
    aggregate_id: str,
    session: Session = Depends(get_session),
):
    """Delete an aggregate."""
    aggregate = session.get(AggregateTable, aggregate_id)
    if not aggregate:
        raise HTTPException(status_code=404, detail="Aggregate not found")

    session.delete(aggregate)
    session.commit()
    return None


@aggregates_router.post("/bulk", response_model=list[AggregateTable], status_code=201)
def create_bulk_aggregates(
    aggregates: list[AggregateTable],
    session: Session = Depends(get_session),
):
    """Create multiple aggregates at once."""
    import uuid

    created_aggregates = []
    for aggregate in aggregates:
        if not aggregate.id:
            aggregate.id = str(uuid.uuid4())
        created_aggregates.append(aggregate)
    
    for i in range(len(created_aggregates)):
        created_aggregates[i] = AggregateTable.convert_to_model(created_aggregates[i], database=database)
        print(created_aggregates[i].simulation)

    created_aggregates = Aggregate.run(created_aggregates)

    for i in range(len(created_aggregates)):
        created_aggregates[i] = AggregateTable.convert_from_model(created_aggregates[i])
        session.add(created_aggregates[i])

    session.commit()

    # Refresh all aggregates
    for aggregate in created_aggregates:
        session.refresh(aggregate)

    return created_aggregates