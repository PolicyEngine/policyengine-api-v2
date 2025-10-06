import uuid
from datetime import datetime

from pydantic import BaseModel, Field
from sqlmodel import Field as SQLField, SQLModel


class Report(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    label: str
    created_at: datetime | None = None


class ReportTable(SQLModel, table=True, extend_existing=True):
    __tablename__ = "reports"

    id: str = SQLField(
        primary_key=True, default_factory=lambda: str(uuid.uuid4())
    )
    label: str = SQLField(nullable=False)
    created_at: datetime = SQLField(default_factory=datetime.utcnow)
