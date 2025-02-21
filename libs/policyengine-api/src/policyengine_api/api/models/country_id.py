from pydantic import BaseModel, field_validator
from policyengine_api.api.utils.constants import COUNTRIES


class CountryId(BaseModel):
    country_id: str

    @field_validator("country_id", mode="after")
    @classmethod
    def validate_country_id(cls, country: str) -> str:
        if country not in COUNTRIES:
            raise ValueError("Invalid country ID")
        return country
