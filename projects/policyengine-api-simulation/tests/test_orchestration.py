"""
Unit tests for the orchestration module.

Tests the logic for spawning parallel simulations and aggregating results.
"""

import pytest

from src.modal.orchestration import (
    STATE_CODES,
    TEST_STATE_CODES,
    run_national_orchestration,
)
from tests.fixtures.orchestration import create_mock_run_simulation


class TestStateCodeConstants:
    """Tests for state code constant definitions."""

    def test__given_state_codes_constant__then_contains_51_entries(self):
        """STATE_CODES should contain all 50 states plus DC."""
        assert len(STATE_CODES) == 51

    def test__given_state_codes_constant__then_contains_dc(self):
        """STATE_CODES should include DC (District of Columbia)."""
        assert "DC" in STATE_CODES

    def test__given_state_codes_constant__then_all_uppercase(self):
        """All state codes should be uppercase."""
        for code in STATE_CODES:
            assert code == code.upper(), f"State code {code} should be uppercase"

    def test__given_test_state_codes_constant__then_contains_10_entries(self):
        """TEST_STATE_CODES should contain exactly 10 states."""
        assert len(TEST_STATE_CODES) == 10

    def test__given_test_state_codes_constant__then_all_in_state_codes(self):
        """All test state codes should be valid state codes."""
        for code in TEST_STATE_CODES:
            assert code in STATE_CODES, f"Test state {code} not in STATE_CODES"


class TestRunNationalOrchestration:
    """Tests for the run_national_orchestration function."""

    def test__given_successful_simulations__then_returns_aggregated_results(self):
        """
        Given all simulations complete successfully
        When orchestration runs
        Then results contain national data plus all district breakdowns.
        """
        # Given
        national_result = {
            "budget": {"baseline": 1000, "reform": 1100},
            "poverty": {"baseline": 0.12, "reform": 0.11},
            "inequality": {"gini": 0.4},
        }
        tx_districts = [
            {"district": "TX-01", "average_household_income_change": 500},
            {"district": "TX-02", "average_household_income_change": 600},
        ]
        ny_districts = [
            {"district": "NY-01", "average_household_income_change": 400},
        ]

        mock_results = {
            "us": national_result,
            "state/tx": {"congressional_district_impact": {"districts": tx_districts}},
            "state/ny": {"congressional_district_impact": {"districts": ny_districts}},
        }
        mock_run_simulation = create_mock_run_simulation(mock_results)

        params = {"reform": {"some.param": True}, "time_period": 2024}

        # When
        result = run_national_orchestration(
            params, mock_run_simulation, state_codes=["TX", "NY"]
        )

        # Then
        assert "budget" in result
        assert "poverty" in result
        assert "inequality" in result
        assert "congressional_district_impact" in result

        district_impact = result["congressional_district_impact"]
        assert len(district_impact["districts"]) == 3
        assert district_impact["failed_states"] is None
        assert set(district_impact["successful_states"]) == {"TX", "NY"}

    def test__given_partial_state_failures__then_returns_successful_districts(self):
        """
        Given some state simulations fail
        When orchestration runs
        Then results include successful districts and list failed states.
        """
        # Given
        national_result = {"budget": {"baseline": 1000}}
        tx_districts = [{"district": "TX-01", "average_household_income_change": 500}]

        mock_results = {
            "us": national_result,
            "state/tx": {"congressional_district_impact": {"districts": tx_districts}},
            "state/ny": RuntimeError("Simulation failed"),
        }
        mock_run_simulation = create_mock_run_simulation(mock_results)

        params = {"reform": {"some.param": True}}

        # When
        result = run_national_orchestration(
            params, mock_run_simulation, state_codes=["TX", "NY"]
        )

        # Then
        district_impact = result["congressional_district_impact"]
        assert len(district_impact["districts"]) == 1
        assert district_impact["districts"][0]["district"] == "TX-01"
        assert district_impact["failed_states"] == ["NY"]
        assert district_impact["successful_states"] == ["TX"]

    def test__given_all_states_fail__then_raises_runtime_error(self):
        """
        Given all state simulations fail
        When orchestration runs
        Then a RuntimeError is raised.
        """
        # Given
        national_result = {"budget": {"baseline": 1000}}

        mock_results = {
            "us": national_result,
            "state/tx": RuntimeError("TX failed"),
            "state/ny": RuntimeError("NY failed"),
        }
        mock_run_simulation = create_mock_run_simulation(mock_results)

        params = {"reform": {"some.param": True}}

        # When / Then
        with pytest.raises(RuntimeError, match="All 2 state simulations failed"):
            run_national_orchestration(
                params, mock_run_simulation, state_codes=["TX", "NY"]
            )

    def test__given_data_param_in_input__then_removes_data_from_spawned_params(self):
        """
        Given params contain 'data' key (used for routing)
        When orchestration spawns simulations
        Then 'data' key is removed from spawned params.
        """
        # Given
        national_result = {"budget": {}}
        tx_result = {"congressional_district_impact": {"districts": []}}

        mock_results = {"us": national_result, "state/tx": tx_result}
        mock_run_simulation = create_mock_run_simulation(mock_results)

        params = {
            "reform": {"some.param": True},
            "data": "national-with-breakdowns",  # This should be stripped
        }

        # When
        run_national_orchestration(
            params, mock_run_simulation, state_codes=["TX"]
        )

        # Then - verify spawn was called without 'data' in params
        spawn_calls = mock_run_simulation.spawn.call_args_list
        for spawn_call in spawn_calls:
            spawned_params = spawn_call[0][0]
            assert "data" not in spawned_params, (
                f"'data' should be removed from spawned params: {spawned_params}"
            )

    def test__given_no_state_codes_specified__then_uses_all_51_states(self):
        """
        Given state_codes is None
        When orchestration runs
        Then it spawns simulations for all 51 states.
        """
        # Given
        national_result = {"budget": {}}
        # Create results for all states
        mock_results = {"us": national_result}
        for state_code in STATE_CODES:
            mock_results[f"state/{state_code.lower()}"] = {
                "congressional_district_impact": {"districts": []}
            }

        mock_run_simulation = create_mock_run_simulation(mock_results)
        params = {"reform": {}}

        # When
        result = run_national_orchestration(
            params, mock_run_simulation, state_codes=None
        )

        # Then
        # 1 national + 51 state spawns = 52 total
        assert mock_run_simulation.spawn.call_count == 52

    def test__given_state_returns_empty_districts__then_handles_gracefully(self):
        """
        Given a state simulation returns empty districts list
        When orchestration runs
        Then the empty list is handled without error.
        """
        # Given
        national_result = {"budget": {}}
        mock_results = {
            "us": national_result,
            "state/tx": {"congressional_district_impact": {"districts": []}},
        }
        mock_run_simulation = create_mock_run_simulation(mock_results)

        params = {"reform": {}}

        # When
        result = run_national_orchestration(
            params, mock_run_simulation, state_codes=["TX"]
        )

        # Then
        assert result["congressional_district_impact"]["districts"] == []
        assert result["congressional_district_impact"]["successful_states"] == ["TX"]

    def test__given_state_missing_district_impact_key__then_handles_gracefully(self):
        """
        Given a state result is missing congressional_district_impact
        When orchestration runs
        Then it extracts empty districts without error.
        """
        # Given
        national_result = {"budget": {}}
        mock_results = {
            "us": national_result,
            "state/tx": {"some_other_key": "value"},  # Missing district impact
        }
        mock_run_simulation = create_mock_run_simulation(mock_results)

        params = {"reform": {}}

        # When
        result = run_national_orchestration(
            params, mock_run_simulation, state_codes=["TX"]
        )

        # Then
        assert result["congressional_district_impact"]["districts"] == []
        assert result["congressional_district_impact"]["successful_states"] == ["TX"]

    def test__given_params_with_region__then_overrides_region_for_each_spawn(self):
        """
        Given base params already contain a region
        When orchestration spawns simulations
        Then the region is overridden appropriately for each spawn.
        """
        # Given
        national_result = {"budget": {}}
        tx_result = {"congressional_district_impact": {"districts": []}}

        mock_results = {"us": national_result, "state/tx": tx_result}
        mock_run_simulation = create_mock_run_simulation(mock_results)

        params = {
            "reform": {},
            "region": "some-other-region",  # Should be overridden
        }

        # When
        run_national_orchestration(
            params, mock_run_simulation, state_codes=["TX"]
        )

        # Then - verify correct regions were used
        spawn_calls = mock_run_simulation.spawn.call_args_list
        regions_used = [call[0][0]["region"] for call in spawn_calls]
        assert "us" in regions_used
        assert "state/tx" in regions_used
