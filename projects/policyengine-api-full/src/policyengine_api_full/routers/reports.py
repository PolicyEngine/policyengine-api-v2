from fastapi import APIRouter, HTTPException, Depends, Query
from sqlmodel import Session, select
from policyengine.database import AggregateTable
from policyengine_api_full.models import ReportTable, ReportElementTable
from policyengine_api_full.database import get_session
from datetime import datetime, timezone
from pydantic import BaseModel
from typing import Optional

reports_router = APIRouter(prefix="/reports", tags=["reports"])


class ReportUpdateRequest(BaseModel):
    """Request model for updating a report."""

    label: Optional[str] = None


@reports_router.get("/", response_model=list[ReportTable])
def list_reports(
    session: Session = Depends(get_session),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=10_000),
):
    """List all reports with pagination."""
    statement = select(ReportTable).offset(skip).limit(limit)
    reports = session.exec(statement).all()
    return reports


@reports_router.post("/", response_model=ReportTable, status_code=201)
def create_report(
    report: ReportTable,
    session: Session = Depends(get_session),
    user_id: Optional[str] = Query(None, description="User ID to automatically associate with this report"),
):
    """Create a new report. Optionally associate with a user by passing user_id query param."""
    from policyengine_api_full.models import UserReportTable
    import uuid

    if not report.id:
        report.id = str(uuid.uuid4())

    report.created_at = datetime.now(timezone.utc)

    session.add(report)
    session.commit()
    session.refresh(report)

    # Auto-create user association if user_id provided
    if user_id:
        user_report = UserReportTable(
            user_id=user_id,
            report_id=report.id,
            is_creator=True,
        )
        session.add(user_report)
        session.commit()

    return report


@reports_router.get("/{report_id}", response_model=ReportTable)
def get_report(
    report_id: str,
    session: Session = Depends(get_session),
):
    """Get a single report by ID."""
    report = session.get(ReportTable, report_id)
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")
    return report


@reports_router.get("/{report_id}/elements", response_model=list[ReportElementTable])
def get_report_elements(
    report_id: str,
    session: Session = Depends(get_session),
):
    """Get all report elements for a specific report."""
    # First check if the report exists
    report = session.get(ReportTable, report_id)
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")

    # Get all report elements for this report, ordered by position
    statement = (
        select(ReportElementTable)
        .where(ReportElementTable.report_id == report_id)
        .order_by(ReportElementTable.position)
    )

    report_elements = session.exec(statement).all()
    return report_elements


@reports_router.patch("/{report_id}", response_model=ReportTable)
def update_report(
    report_id: str,
    update_request: ReportUpdateRequest,
    session: Session = Depends(get_session),
):
    """Update a report."""
    db_report = session.get(ReportTable, report_id)
    if not db_report:
        raise HTTPException(status_code=404, detail="Report not found")

    if update_request.label is not None:
        db_report.label = update_request.label

    session.add(db_report)
    session.commit()
    session.refresh(db_report)
    return db_report


@reports_router.delete("/{report_id}", status_code=204)
def delete_report(
    report_id: str,
    session: Session = Depends(get_session),
):
    """Delete a report and its associated report elements."""
    report = session.get(ReportTable, report_id)
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")

    # First delete all associated report elements
    statement = select(ReportElementTable).where(
        ReportElementTable.report_id == report_id
    )
    report_elements = session.exec(statement).all()

    # Delete each report element (this will also handle their aggregates)
    for element in report_elements:
        # Delete associated aggregates first
        agg_statement = select(AggregateTable).where(
            AggregateTable.reportelement_id == element.id
        )
        aggregates = session.exec(agg_statement).all()
        for aggregate in aggregates:
            session.delete(aggregate)

        session.delete(element)

    # Now delete the report itself
    session.delete(report)
    session.commit()
    return None
