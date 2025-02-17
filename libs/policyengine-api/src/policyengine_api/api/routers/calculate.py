from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, SQLModel, Field
from policyengine_api.fastapi.database import SessionGeneratorFactory
from policyengine_api.api.models.country_id import CountryId
from policyengine_api.api.models.household import (
    HouseholdDataUS,
    HouseholdDataUK,
    HouseholdDataGeneric,
)
from policyengine_api.api.utils.constants import COUNTRIES
import logging
from typing import Any


def create_router():
    router = APIRouter()

    @router.post("/country_id/calculate")
    async def calculate(
        country_id: CountryId,
        household_json: dict = {},
        policy_json: dict = {},
    ):
        # In future - disambiguate between inbound household JSON items, outbound household
        # schemas, and the actual household data model - need to confirm with others

        # Schemas for household_json, policy_json
        country = COUNTRIES.get(country_id)

        # What does result even look like?
        result_raw: dict[str, Any] = country.calculate(
            household_json, policy_json
        )
        if country_id == "us":
            result = HouseholdDataUS.model_validate(result_raw)
        elif country_id == "uk":
            result = HouseholdDataUK.model_validate(result_raw)
        else:
            result = HouseholdDataGeneric.model_validate(result_raw)
        return result
