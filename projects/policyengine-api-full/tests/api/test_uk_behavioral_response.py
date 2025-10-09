"""
Test UK behavioral response (labor supply response) functionality.

This test verifies that when behavioral response parameters are present in a reform,
the API automatically calls apply_dynamics() to enable behavioral adjustments.
"""

from unittest.mock import MagicMock, patch


def test_uk_behavioral_response_calls_apply_dynamics():
    """
    Test that apply_dynamics is called when behavioral response parameters are present.

    This test would have failed before the PR fix because the API wasn't detecting
    behavioral response parameters and calling apply_dynamics().
    """
    from policyengine_api_full.api.models.household import HouseholdUK
    from policyengine_api_full.api.country import PolicyEngineCountry

    household_data = {
        "people": {"person": {"age": {"2025": 30}}},
        "benunits": {"benunit": {"members": ["person"]}},
        "households": {"household": {"members": ["person"]}},
    }

    reform_with_behavioral = {
        "gov.simulation.labor_supply_responses.income_elasticity": {
            "2025-01-01.2100-12-31": 0.1
        },
    }

    household = HouseholdUK(**household_data)

    # Create UK country instance directly to avoid loading all countries
    uk_country = PolicyEngineCountry("policyengine_uk", "uk")

    # Mock the Simulation class to verify apply_dynamics is called
    with patch.object(uk_country.country_package, "Simulation") as MockSimulation:
        # Create mock simulation instance
        mock_sim = MagicMock()
        mock_sim.calculate.return_value = [30]
        mock_sim.get_population.return_value.get_index.return_value = 0
        mock_sim.apply_dynamics = MagicMock()  # This is what we want to verify

        MockSimulation.return_value = mock_sim

        uk_country.calculate(household=household, reform=reform_with_behavioral)

        # Verify apply_dynamics was called with the correct year
        mock_sim.apply_dynamics.assert_called_once_with(year=2025)


def test_uk_without_behavioral_response_no_apply_dynamics():
    """
    Test that apply_dynamics is NOT called when behavioral response parameters are absent.
    """
    from policyengine_api_full.api.models.household import HouseholdUK
    from policyengine_api_full.api.country import PolicyEngineCountry

    household_data = {
        "people": {"person": {"age": {"2025": 30}}},
        "benunits": {"benunit": {"members": ["person"]}},
        "households": {"household": {"members": ["person"]}},
    }

    reform_without_behavioral = {
        "gov.hmrc.income_tax.rates.uk[0].rate": {"2025-01-01.2100-12-31": 0.25},
    }

    household = HouseholdUK(**household_data)
    uk_country = PolicyEngineCountry("policyengine_uk", "uk")

    with patch.object(uk_country.country_package, "Simulation") as MockSimulation:
        mock_sim = MagicMock()
        mock_sim.calculate.return_value = [30]
        mock_sim.get_population.return_value.get_index.return_value = 0
        mock_sim.apply_dynamics = MagicMock()

        MockSimulation.return_value = mock_sim

        uk_country.calculate(household=household, reform=reform_without_behavioral)

        # Verify apply_dynamics was NOT called
        mock_sim.apply_dynamics.assert_not_called()
