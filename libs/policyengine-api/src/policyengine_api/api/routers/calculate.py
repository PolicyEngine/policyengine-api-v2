from fastapi import APIRouter
from policyengine_api.api.enums import COUNTRY_ID
from policyengine_api.api.models.household import (
    HouseholdDataUS,
    HouseholdDataUK,
    HouseholdDataGeneric,
)
from policyengine_api.api.country import COUNTRIES


router = APIRouter()


@router.post("/{country_id}/calculate")
async def calculate(
    country_id: COUNTRY_ID,
    household: HouseholdDataGeneric | HouseholdDataUK | HouseholdDataUS = {},
    policy: dict = {},
) -> HouseholdDataGeneric | HouseholdDataUK | HouseholdDataUS:

    country = COUNTRIES.get(country_id.value)

    result: HouseholdDataGeneric | HouseholdDataUK | HouseholdDataUS = (
        country.calculate(household, policy)
    )
    return result
