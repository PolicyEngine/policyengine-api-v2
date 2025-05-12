from fastapi import APIRouter
from policyengine_api.api.enums import COUNTRY_ID
from policyengine_api.api.models.calculation_request import CalculationRequest

router = APIRouter()

@router.post("/{country_id}/test")
async def test_endpoint(country_id: COUNTRY_ID, request: CalculationRequest) -> str:
    """
    Test endpoint to verify the API is working.
    """
    return f"Test endpoint for country ID: {country_id.value}"
