from fastapi import APIRouter, HTTPException, Depends, Query, Body
from sqlmodel import Session, select
from policyengine.database import ReportElementTable, AggregateTable
from policyengine.models import Aggregate
from policyengine_api_full.database import get_session
from typing import Optional, List, Dict, Any
from datetime import datetime, timezone
from pydantic import BaseModel

report_elements_router = APIRouter(prefix="/report-elements", tags=["report elements"])


class AggregateInput(BaseModel):
    """Input model for aggregate data without the value field."""
    entity: str
    variable_name: str
    aggregate_function: str  # "sum", "mean", or "count"
    simulation_id: str
    year: Optional[int] = None
    filter_variable_name: Optional[str] = None
    filter_variable_value: Optional[str] = None
    filter_variable_leq: Optional[float] = None
    filter_variable_geq: Optional[float] = None


class ReportElementCreateRequest(BaseModel):
    """Request model for creating a report element with associated data."""
    label: str
    type: str  # "chart", "markdown", or "aggregates"
    data_type: Optional[str] = None  # "Aggregate" when creating aggregates
    data: Optional[List[AggregateInput]] = None  # List of aggregates to compute
    chart_type: Optional[str] = None
    x_axis_variable: Optional[str] = None
    y_axis_variable: Optional[str] = None
    group_by: Optional[str] = None
    color_by: Optional[str] = None
    size_by: Optional[str] = None
    markdown_content: Optional[str] = None
    report_id: Optional[str] = None
    user_id: Optional[str] = None
    position: Optional[int] = None
    visible: Optional[bool] = True


@report_elements_router.get("/", response_model=list[ReportElementTable])
def list_report_elements(
    session: Session = Depends(get_session),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=10_000),
    report_id: Optional[str] = Query(None, description="Filter by report ID"),
    user_id: Optional[str] = Query(None, description="Filter by user ID"),
):
    """List all report elements with pagination and optional filters."""
    statement = select(ReportElementTable)

    if report_id:
        statement = statement.where(ReportElementTable.report_id == report_id)
    if user_id:
        statement = statement.where(ReportElementTable.user_id == user_id)

    statement = statement.offset(skip).limit(limit)

    if report_id:
        statement = statement.order_by(ReportElementTable.position)

    report_elements = session.exec(statement).all()
    return report_elements


@report_elements_router.post("/", response_model=Dict[str, Any], status_code=201)
def create_report_element(
    request: ReportElementCreateRequest,
    session: Session = Depends(get_session),
):
    """
    Create a new report element.

    If data_type is "Aggregate" and data is provided, this will:
    1. Create the report element
    2. Run Aggregate.run() on the provided aggregates
    3. Save the computed aggregates to the database
    4. Return the report element with the computed aggregate values
    """
    import uuid
    from policyengine.database import SimulationTable

    # Create the report element
    report_element = ReportElementTable(
        id=str(uuid.uuid4()),
        label=request.label,
        type=request.type,
        data_table="aggregates" if request.data_type == "Aggregate" else None,
        chart_type=request.chart_type,
        x_axis_variable=request.x_axis_variable,
        y_axis_variable=request.y_axis_variable,
        group_by=request.group_by,
        color_by=request.color_by,
        size_by=request.size_by,
        markdown_content=request.markdown_content,
        report_id=request.report_id,
        user_id=request.user_id,
        position=request.position,
        visible=request.visible,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc)
    )

    session.add(report_element)
    session.flush()  # Get the ID before processing aggregates

    computed_aggregates = []

    # Process aggregates if provided
    if request.data_type == "Aggregate" and request.data:
        # Convert input aggregates to Aggregate model instances
        aggregate_models = []

        for agg_input in request.data:
            # Get the simulation
            simulation_table = session.get(SimulationTable, agg_input.simulation_id)
            if not simulation_table:
                raise HTTPException(
                    status_code=400,
                    detail=f"Simulation {agg_input.simulation_id} not found"
                )

            # Convert simulation table to model (we need the full simulation object)
            from policyengine.database import Database
            from policyengine_api_full.database import engine

            # Create a database instance to handle the conversion
            db = Database.from_engine(engine)
            simulation = simulation_table.convert_to_model(db)

            # Create the Aggregate model instance
            agg = Aggregate(
                simulation=simulation,
                entity=agg_input.entity,
                variable_name=agg_input.variable_name,
                year=agg_input.year,
                filter_variable_name=agg_input.filter_variable_name,
                filter_variable_value=agg_input.filter_variable_value,
                filter_variable_leq=agg_input.filter_variable_leq,
                filter_variable_geq=agg_input.filter_variable_geq,
                aggregate_function=agg_input.aggregate_function,
                reportelement_id=report_element.id
            )
            aggregate_models.append(agg)

        # Run Aggregate.run to compute values
        computed_models = Aggregate.run(aggregate_models)

        # Save the computed aggregates to the database
        for agg_model in computed_models:
            agg_table = AggregateTable(
                id=agg_model.id,
                simulation_id=agg_model.simulation.id if agg_model.simulation else None,
                entity=agg_model.entity,
                variable_name=agg_model.variable_name,
                year=agg_model.year,
                filter_variable_name=agg_model.filter_variable_name,
                filter_variable_value=agg_model.filter_variable_value,
                filter_variable_leq=agg_model.filter_variable_leq,
                filter_variable_geq=agg_model.filter_variable_geq,
                aggregate_function=agg_model.aggregate_function,
                reportelement_id=report_element.id,
                value=agg_model.value
            )
            session.add(agg_table)
            computed_aggregates.append({
                "id": agg_table.id,
                "entity": agg_table.entity,
                "variable_name": agg_table.variable_name,
                "aggregate_function": agg_table.aggregate_function,
                "value": agg_table.value,
                "year": agg_table.year,
                "filter_variable_name": agg_table.filter_variable_name,
                "filter_variable_value": agg_table.filter_variable_value,
                "filter_variable_leq": agg_table.filter_variable_leq,
                "filter_variable_geq": agg_table.filter_variable_geq,
            })

    session.commit()
    session.refresh(report_element)

    # Return the report element with computed aggregates
    response = {
        "report_element": {
            "id": report_element.id,
            "label": report_element.label,
            "type": report_element.type,
            "data_table": report_element.data_table,
            "chart_type": report_element.chart_type,
            "x_axis_variable": report_element.x_axis_variable,
            "y_axis_variable": report_element.y_axis_variable,
            "group_by": report_element.group_by,
            "color_by": report_element.color_by,
            "size_by": report_element.size_by,
            "markdown_content": report_element.markdown_content,
            "report_id": report_element.report_id,
            "user_id": report_element.user_id,
            "position": report_element.position,
            "visible": report_element.visible,
            "created_at": report_element.created_at.isoformat(),
            "updated_at": report_element.updated_at.isoformat(),
        }
    }

    if computed_aggregates:
        response["aggregates"] = computed_aggregates

    return response


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
    label: Optional[str] = None,
    type: Optional[str] = None,
    chart_type: Optional[str] = None,
    x_axis_variable: Optional[str] = None,
    y_axis_variable: Optional[str] = None,
    group_by: Optional[str] = None,
    color_by: Optional[str] = None,
    size_by: Optional[str] = None,
    markdown_content: Optional[str] = None,
    position: Optional[int] = None,
    visible: Optional[bool] = None,
    session: Session = Depends(get_session),
):
    """Update a report element."""
    db_report_element = session.get(ReportElementTable, report_element_id)
    if not db_report_element:
        raise HTTPException(status_code=404, detail="Report element not found")

    if label is not None:
        db_report_element.label = label
    if type is not None:
        db_report_element.type = type
    if chart_type is not None:
        db_report_element.chart_type = chart_type
    if x_axis_variable is not None:
        db_report_element.x_axis_variable = x_axis_variable
    if y_axis_variable is not None:
        db_report_element.y_axis_variable = y_axis_variable
    if group_by is not None:
        db_report_element.group_by = group_by
    if color_by is not None:
        db_report_element.color_by = color_by
    if size_by is not None:
        db_report_element.size_by = size_by
    if markdown_content is not None:
        db_report_element.markdown_content = markdown_content
    if position is not None:
        db_report_element.position = position
    if visible is not None:
        db_report_element.visible = visible

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
    """Delete a report element and its associated aggregates."""
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

    session.delete(report_element)
    session.commit()
    return None