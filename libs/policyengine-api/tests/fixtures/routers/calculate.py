import pytest
from unittest.mock import patch
from copy import deepcopy
from fastapi.testclient import TestClient
from policyengine_api.api.routers.calculate import router as calculate_router
from policyengine_api.api.models.household import HouseholdUS
from policyengine_api.api.data.examples.example_household import (
    example_household_output_us,
)
from ...fixtures.common import createApi


@pytest.fixture
def client() -> TestClient:
    api = createApi(calculate_router)
    return TestClient(api)


@pytest.fixture
def mock_calculate_method():
    """Mock the calculation method."""
    with patch(
        "policyengine_api.api.routers.calculate.COUNTRIES"
    ) as mock_countries:

        class MockCountry:
            def calculate(self, household, reform):
                return HouseholdUS(**example_household_output_us)

        mock_countries.get.return_value = MockCountry()
        yield mock_countries
