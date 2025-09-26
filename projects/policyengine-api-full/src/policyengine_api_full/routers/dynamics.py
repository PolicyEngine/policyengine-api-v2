from fastapi import APIRouter, HTTPException, Depends, Query
from sqlmodel import Session, select
from policyengine.database import DynamicTable
from policyengine_api_full.database import get_session
from typing import Optional

router = APIRouter(prefix="/dynamics", tags=["dynamics"])


@router.get("/", response_model=list[DynamicTable])
def list_dynamics(
    session: Session = Depends(get_session),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
):
    """List all dynamics with pagination."""
    statement = select(DynamicTable).offset(skip).limit(limit)
    dynamics = session.exec(statement).all()
    return dynamics


@router.post("/", response_model=DynamicTable, status_code=201)
def create_dynamic(
    dynamic: DynamicTable,
    session: Session = Depends(get_session),
):
    """Create a new dynamic."""
    session.add(dynamic)
    session.commit()
    session.refresh(dynamic)
    return dynamic


@router.get("/{dynamic_id}", response_model=DynamicTable)
def get_dynamic(
    dynamic_id: str,
    session: Session = Depends(get_session),
):
    """Get a single dynamic by ID."""
    dynamic = session.get(DynamicTable, dynamic_id)
    if not dynamic:
        raise HTTPException(status_code=404, detail="Dynamic not found")
    return dynamic


@router.patch("/{dynamic_id}", response_model=DynamicTable)
def update_dynamic(
    dynamic_id: str,
    name: Optional[str] = None,
    description: Optional[str] = None,
    years: Optional[list[int]] = None,
    session: Session = Depends(get_session),
):
    """Update a dynamic."""
    db_dynamic = session.get(DynamicTable, dynamic_id)
    if not db_dynamic:
        raise HTTPException(status_code=404, detail="Dynamic not found")

    if name is not None:
        db_dynamic.name = name
    if description is not None:
        db_dynamic.description = description
    if years is not None:
        db_dynamic.years = years

    session.add(db_dynamic)
    session.commit()
    session.refresh(db_dynamic)
    return db_dynamic


@router.delete("/{dynamic_id}", status_code=204)
def delete_dynamic(
    dynamic_id: str,
    session: Session = Depends(get_session),
):
    """Delete a dynamic."""
    dynamic = session.get(DynamicTable, dynamic_id)
    if not dynamic:
        raise HTTPException(status_code=404, detail="Dynamic not found")

    session.delete(dynamic)
    session.commit()
    return None