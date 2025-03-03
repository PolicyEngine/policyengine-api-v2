from fastapi import APIRouter
from policyengine_api.api.enums import COUNTRY_ID
from policyengine_api.api.models.household import (
    HouseholdUS,
    HouseholdUK,
    HouseholdGeneric,
)
from policyengine_api.api.country import COUNTRIES


router = APIRouter()


@router.post("/{country_id}/calculate")
async def calculate(
    country_id: COUNTRY_ID,
    household: HouseholdGeneric | HouseholdUK | HouseholdUS = {},
    policy: dict = {},
) -> HouseholdGeneric | HouseholdUK | HouseholdUS:

    # Household models above currently conflict with models defined in
    # household/household.py; the household routes will be brought in 
    # line in later iteration
    country = COUNTRIES.get(country_id.value)

    result: HouseholdGeneric | HouseholdUK | HouseholdUS = (
        country.calculate(household, policy)
    )
    return result
