import pytest
from unittest.mock import patch
from copy import deepcopy
from policyengine_api.api.models.household import HouseholdUS
from policyengine_api.api.data.examples.example_household import example_household_output_us

@pytest.fixture
def mock_calculate_method():
    """Mock the calculation method."""
    with patch(
        "policyengine_api.api.country.COUNTRIES.get"
    ) as mock:
        sample_return_value = deepcopy(example_household_output_us)
        mock.return_value.calculate.return_value = HouseholdUS(**sample_return_value)
        yield mock