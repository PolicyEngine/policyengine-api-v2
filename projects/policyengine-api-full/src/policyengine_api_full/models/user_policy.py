from datetime import datetime
from uuid import uuid4

from sqlmodel import Field, SQLModel


class UserPolicyTable(SQLModel, table=True, extend_existing=True):
    __tablename__ = "user_policies"

    id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True)
    user_id: str = Field(foreign_key="users.id", nullable=False)
    policy_id: str = Field(foreign_key="policies.id", nullable=False)
    custom_name: str | None = Field(default=None)
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
