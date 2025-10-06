import uuid
from datetime import datetime

from pydantic import BaseModel, Field
from sqlmodel import Field as SQLField, SQLModel


class User(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    username: str
    first_name: str | None = None
    last_name: str | None = None
    email: str | None = None
    current_model_id: str = "policyengine_uk"
    created_at: datetime | None = None
    updated_at: datetime | None = None


class UserTable(SQLModel, table=True, extend_existing=True):
    __tablename__ = "users"

    id: str = SQLField(
        primary_key=True, default_factory=lambda: str(uuid.uuid4())
    )
    username: str = SQLField(nullable=False, unique=True)
    first_name: str | None = SQLField(default=None)
    last_name: str | None = SQLField(default=None)
    email: str | None = SQLField(default=None)
    current_model_id: str = SQLField(default="policyengine_uk")
    created_at: datetime = SQLField(default_factory=datetime.utcnow)
    updated_at: datetime = SQLField(default_factory=datetime.utcnow)
