from fastapi import APIRouter, Depends
from policyengine_api.api.utils.enums import CountryId
from policyengine_api.api.models.metadata import MetadataModule
from policyengine_api.api.country import COUNTRIES

router = APIRouter()


@router.get("/{country_id}/metadata")
async def metadata(country_id: CountryId) -> MetadataModule:
    country = COUNTRIES.get(country_id.value)
    return country.metadata
