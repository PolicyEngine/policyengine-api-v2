from fastapi import APIRouter, HTTPException, Depends, Query, Body
from sqlmodel import Session, select
from policyengine.database import AggregateTable, AggregateChangeTable
from policyengine.models import Aggregate, AggregateChange
from policyengine_api_full.models import ReportElementTable
from policyengine_api_full.database import get_session, database
from typing import Optional, Dict, Any
from datetime import datetime, timezone
from pydantic import BaseModel
import time

# Import AI functions
from .report_elements_ai import (
    AIReportElementRequest,
    AIReportElementResponse,
    AIProcessRequest,
    AIProcessResponse,
    create_ai_report_element as ai_create_element,
    process_with_ai as ai_process,
)

report_elements_router = APIRouter(prefix="/report-elements", tags=["report elements"])


class AggregateInput(BaseModel):
    """Input model for aggregate data without the value field."""
    entity: Optional[str] = None
    variable_name: str
    aggregate_function: str  # "sum", "mean", or "count"
    simulation_id: str
    year: Optional[int] = None
    filter_variable_name: Optional[str] = None
    filter_variable_value: Optional[str] = None
    filter_variable_leq: Optional[float] = None
    filter_variable_geq: Optional[float] = None


class AggregateChangeInput(BaseModel):
    """Input model for aggregate change data."""
    entity: Optional[str] = None
    variable_name: str
    aggregate_function: str  # "sum", "mean", or "count"
    baseline_simulation_id: str
    comparison_simulation_id: str
    year: Optional[int] = None
    filter_variable_name: Optional[str] = None
    filter_variable_value: Optional[str] = None
    filter_variable_leq: Optional[float] = None
    filter_variable_geq: Optional[float] = None


class ReportElementCreateRequest(BaseModel):
    """Request model for creating a report element with associated data."""
    label: str
    type: str  # "data" or "markdown"
    markdown_content: Optional[str] = None
    report_id: Optional[str] = None
    position: Optional[int] = None
    # For AI-processed content (created separately via AI endpoints)
    processed_output_type: Optional[str] = None
    processed_output: Optional[str] = None


class ReportElementUpdateRequest(BaseModel):
    """Request model for updating a report element."""
    label: Optional[str] = None
    type: Optional[str] = None
    markdown_content: Optional[str] = None
    position: Optional[int] = None
    processed_output_type: Optional[str] = None
    processed_output: Optional[str] = None


@report_elements_router.get("/", response_model=list[ReportElementTable])
def list_report_elements(
    session: Session = Depends(get_session),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=10_000),
    report_id: Optional[str] = Query(None, description="Filter by report ID"),
):
    """List all report elements with pagination and optional filters."""
    statement = select(ReportElementTable)

    if report_id:
        statement = statement.where(ReportElementTable.report_id == report_id)

    statement = statement.offset(skip).limit(limit)

    if report_id:
        statement = statement.order_by(ReportElementTable.position)

    report_elements = session.exec(statement).all()
    return report_elements


@report_elements_router.post("/", response_model=ReportElementTable)
def create_report_element(
    request: ReportElementCreateRequest,
    session: Session = Depends(get_session),
):
    """
    Create a new report element (markdown or data).
    For data elements, aggregates are created separately via the AI endpoint.
    """
    import uuid

    # Create the report element
    report_element = ReportElementTable(
        id=str(uuid.uuid4()),
        label=request.label,
        type=request.type,
        markdown_content=request.markdown_content,
        report_id=request.report_id,
        position=request.position,
        processed_output_type=request.processed_output_type,
        processed_output=request.processed_output,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc)
    )

    session.add(report_element)
    session.commit()
    session.refresh(report_element)

    return report_element


@report_elements_router.get("/{report_element_id}", response_model=ReportElementTable)
def get_report_element(
    report_element_id: str,
    session: Session = Depends(get_session),
):
    """Get a single report element by ID."""
    report_element = session.get(ReportElementTable, report_element_id)
    if not report_element:
        raise HTTPException(status_code=404, detail="Report element not found")
    return report_element


@report_elements_router.get("/{report_element_id}/aggregates", response_model=list[AggregateTable])
def get_report_element_aggregates(
    report_element_id: str,
    session: Session = Depends(get_session),
):
    """Get all aggregates associated with a report element."""
    # First check if the report element exists
    report_element = session.get(ReportElementTable, report_element_id)
    if not report_element:
        raise HTTPException(status_code=404, detail="Report element not found")

    # Get all aggregates for this report element
    statement = select(AggregateTable).where(
        AggregateTable.reportelement_id == report_element_id
    )
    aggregates = session.exec(statement).all()
    return aggregates


@report_elements_router.patch("/{report_element_id}", response_model=ReportElementTable)
def update_report_element(
    report_element_id: str,
    update_request: ReportElementUpdateRequest,
    session: Session = Depends(get_session),
):
    """Update a report element."""
    db_report_element = session.get(ReportElementTable, report_element_id)
    if not db_report_element:
        raise HTTPException(status_code=404, detail="Report element not found")

    if update_request.label is not None:
        db_report_element.label = update_request.label
    if update_request.type is not None:
        db_report_element.type = update_request.type
    if update_request.markdown_content is not None:
        db_report_element.markdown_content = update_request.markdown_content
    if update_request.position is not None:
        db_report_element.position = update_request.position
    if update_request.processed_output_type is not None:
        db_report_element.processed_output_type = update_request.processed_output_type
    if update_request.processed_output is not None:
        db_report_element.processed_output = update_request.processed_output

    db_report_element.updated_at = datetime.now(timezone.utc)

    session.add(db_report_element)
    session.commit()
    session.refresh(db_report_element)
    return db_report_element


@report_elements_router.delete("/{report_element_id}", status_code=204)
def delete_report_element(
    report_element_id: str,
    session: Session = Depends(get_session),
):
    """Delete a report element and its associated aggregates or aggregate changes."""
    report_element = session.get(ReportElementTable, report_element_id)
    if not report_element:
        raise HTTPException(status_code=404, detail="Report element not found")

    # Delete associated aggregates (cascade should handle this, but being explicit)
    statement = select(AggregateTable).where(
        AggregateTable.reportelement_id == report_element_id
    )
    aggregates = session.exec(statement).all()
    for aggregate in aggregates:
        session.delete(aggregate)

    # Delete associated aggregate changes
    statement_changes = select(AggregateChangeTable).where(
        AggregateChangeTable.reportelement_id == report_element_id
    )
    aggregate_changes = session.exec(statement_changes).all()
    for aggregate_change in aggregate_changes:
        session.delete(aggregate_change)

    session.delete(report_element)
    session.commit()
    return None


# AI endpoints - using the imported implementations
@report_elements_router.post("/ai", response_model=AIReportElementResponse)
def create_ai_report_element(
    request: AIReportElementRequest,
    session: Session = Depends(get_session),
):
    """Create a report element using AI to generate data requests."""
    return ai_create_element(request, session)


@report_elements_router.post("/ai/process", response_model=AIProcessResponse)
def process_with_ai(
    request: AIProcessRequest,
    session: Session = Depends(get_session),
):
    """Process report element data with AI to generate visualizations or insights."""
    return ai_process(request, session)