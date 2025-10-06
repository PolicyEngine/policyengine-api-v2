import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field
from sqlmodel import Column, Field as SQLField, JSON, SQLModel


class ReportElement(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    label: str
    type: Literal["chart", "markdown"]
    data_table: Literal["aggregates", "aggregate_changes"] | None = None
    chart_type: (
        Literal["bar", "line", "scatter", "area", "pie", "histogram"] | None
    ) = None
    x_axis_variable: str | None = None
    y_axis_variable: str | None = None
    group_by: str | None = None
    color_by: str | None = None
    size_by: str | None = None
    markdown_content: str | None = None
    report_id: str | None = None
    user_id: str | None = None
    model_version_id: str | None = None
    position: int | None = None
    visible: bool | None = True
    custom_config: dict | None = None
    report_element_metadata: dict | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class ReportElementTable(SQLModel, table=True, extend_existing=True):
    __tablename__ = "report_elements"

    id: str = SQLField(
        primary_key=True, default_factory=lambda: str(uuid.uuid4())
    )
    label: str = SQLField(nullable=False)
    type: str = SQLField(nullable=False)

    # Data source
    data_table: str | None = SQLField(default=None)

    # Chart configuration
    chart_type: str | None = SQLField(default=None)
    x_axis_variable: str | None = SQLField(default=None)
    y_axis_variable: str | None = SQLField(default=None)
    group_by: str | None = SQLField(default=None)
    color_by: str | None = SQLField(default=None)
    size_by: str | None = SQLField(default=None)

    # Markdown specific
    markdown_content: str | None = SQLField(default=None)

    # Metadata
    report_id: str | None = SQLField(default=None, foreign_key="reports.id")
    user_id: str | None = SQLField(default=None, foreign_key="users.id")
    model_version_id: str | None = SQLField(default=None)
    position: int | None = SQLField(default=None)
    visible: bool | None = SQLField(default=True)
    custom_config: dict | None = SQLField(default=None, sa_column=Column(JSON))
    report_element_metadata: dict | None = SQLField(
        default=None, sa_column=Column(JSON)
    )

    created_at: datetime = SQLField(default_factory=datetime.utcnow)
    updated_at: datetime = SQLField(default_factory=datetime.utcnow)
