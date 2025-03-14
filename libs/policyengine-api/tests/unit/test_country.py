from policyengine_api.api.country import PolicyEngineCountry
from policyengine_api.api.data.examples.example_household_us import (
    example_household_input_us,
)
from policyengine_api.api.data.examples.example_household_uk import (
    example_household_input_uk,
)
from policyengine_api.api.models.household import HouseholdUS, HouseholdUK
from ..fixtures.country import is_valid_household


class TestCalculate:

    def test_given_valid_us_input__return_valid_output(self):
        test_country_id = "us"

        country = PolicyEngineCountry(
            f"policyengine_{test_country_id}", test_country_id
        )
        valid_household = HouseholdUS(**example_household_input_us)
        reform = None

        result = country.calculate(valid_household, reform)

        assert result is not None
        assert type(result) == HouseholdUS

        household_dict = result.model_dump()
        assert is_valid_household(household_dict)

    def test_given_valid_uk_input__return_valid_output(self):
        test_country_id = "uk"

        country = PolicyEngineCountry(
            f"policyengine_{test_country_id}", test_country_id
        )
        valid_household = HouseholdUK(**example_household_input_uk)
        reform = None

        result = country.calculate(valid_household, reform)

        assert result is not None
        assert type(result) == HouseholdUK

        household_dict = result.model_dump()
        assert is_valid_household(household_dict)

    # Temporarily disabling due to questions around our existing axes schema -
    # when I emit a front-end request with axes, why is it the HouseholdAxes
    # module defined in this package doubly nested inside two arrays?
    # def test_given_household_with_axes__return_valid_output(self):
    #     test_country_id = "us"

    #     country = PolicyEngineCountry(
    #         f"policyengine_{test_country_id}", test_country_id
    #     )
    #     valid_household = example_household_input_us
    #     valid_axes = {
    #         "name": "employment_income",
    #         "period": "2024",
    #         "count": 11,
    #         "min": 0,
    #         "max": 100000,
    #     }
    #     valid_household["axes"] = valid_axes
    #     serialized_household = HouseholdUS(**valid_household)
    #     reform = None

    #     result = country.calculate(serialized_household, reform)

    #     assert result is not None
    #     assert type(result) == HouseholdUS

    #     household_dict = result.model_dump()
    #     assert is_valid_household(household_dict)
    #     assert "axes" in household_dict.keys()
