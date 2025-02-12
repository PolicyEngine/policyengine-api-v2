from sqlmodel import Field, SQLModel
from typing import Optional
import datetime


class SimulationJobBase(SQLModel):
    """
    Shared fields for SimulationJob used for requests and DB table.
    """

    status: str = "pending"
    created_at: datetime.datetime = datetime.datetime.now(
        datetime.timezone.utc
    )
    completed_at: Optional[datetime.datetime] = None
    input_data: Optional[str] = None
    output_data: Optional[str] = None


class SimulationJob(SimulationJobBase, table=True):
    """
    Primary table for storing simulation job metadata and results.
    """

    id: Optional[int] = Field(default=None, primary_key=True)
