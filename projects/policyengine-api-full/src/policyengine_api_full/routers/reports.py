from fastapi import APIRouter, HTTPException, Depends, Query
from sqlmodel import Session, select
from policyengine.database import ReportTable
from policyengine_api_full.database import get_session
from typing import Optional
from datetime import datetime, timezone

reports_router = APIRouter(prefix="/reports", tags=["reports"])


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
):
    """Create a new report."""
    if not report.id:
        import uuid
        report.id = str(uuid.uuid4())

    report.created_at = datetime.now(timezone.utc)

    session.add(report)
    session.commit()
    session.refresh(report)
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


@reports_router.patch("/{report_id}", response_model=ReportTable)
def update_report(
    report_id: str,
    label: Optional[str] = None,
    session: Session = Depends(get_session),
):
    """Update a report."""
    db_report = session.get(ReportTable, report_id)
    if not db_report:
        raise HTTPException(status_code=404, detail="Report not found")

    if label is not None:
        db_report.label = label

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

    session.delete(report)
    session.commit()
    return None