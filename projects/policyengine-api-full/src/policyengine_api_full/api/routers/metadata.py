from fastapi import APIRouter, Depends
from policyengine_api_full.api.enums import COUNTRY_ID
from policyengine_api_full.api.models.metadata.metadata_module import MetadataModule
from policyengine_api_full.api.country import COUNTRIES

router = APIRouter()


@router.get("/{country_id}/metadata")
async def metadata(country_id: COUNTRY_ID) -> MetadataModule:
    country = COUNTRIES.get(country_id.value)
    return country.metadata
