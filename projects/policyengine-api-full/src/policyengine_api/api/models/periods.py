from pydantic import BaseModel, field_validator
import re


class ISO8601Date(BaseModel):
    date: str

    @field_validator("date", mode="after")
    @classmethod
    def is_iso_8601_date(cls, value: str) -> str:
        if not re.match(r"\d{4}-\d{2}-\d{2}", value):
            raise ValueError("date must be in ISO 8601 format")
        return value
