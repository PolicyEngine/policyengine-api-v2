import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field
from sqlmodel import Column, Field as SQLField, JSON, SQLModel


class ReportElement(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    label: str
    type: Literal["data", "markdown"]
    report_id: str | None = None
    position: int | None = None
    # For markdown type elements
    markdown_content: str | None = None
    # For AI-processed data elements
    processed_output_type: str | None = None
    processed_output: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class ReportElementTable(SQLModel, table=True, extend_existing=True):
    __tablename__ = "report_elements"

    id: str = SQLField(
        primary_key=True, default_factory=lambda: str(uuid.uuid4())
    )
    label: str = SQLField(nullable=False)
    type: str = SQLField(nullable=False)  # 'markdown' or 'data'
    report_id: str | None = SQLField(default=None, foreign_key="reports.id")
    position: int | None = SQLField(default=None)

    # For markdown type elements
    markdown_content: str | None = SQLField(default=None)

    # For AI-processed data elements
    processed_output_type: str | None = SQLField(default=None)  # 'markdown' or 'plotly'
    processed_output: str | None = SQLField(default=None)  # Markdown text or JSON string for plotly

    created_at: datetime = SQLField(default_factory=datetime.utcnow)
    updated_at: datetime = SQLField(default_factory=datetime.utcnow)
