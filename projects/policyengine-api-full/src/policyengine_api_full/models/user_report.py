from datetime import datetime
from uuid import uuid4

from sqlmodel import Field, SQLModel


class UserReportTable(SQLModel, table=True, extend_existing=True):
    __tablename__ = "user_reports"

    id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True)
    user_id: str = Field(foreign_key="users.id", nullable=False)
    report_id: str = Field(foreign_key="reports.id", nullable=False)
    custom_name: str | None = Field(default=None)
    is_creator: bool = Field(default=False)
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
