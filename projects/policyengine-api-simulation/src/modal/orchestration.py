"""
Orchestration logic for national-with-breakdowns simulations.

This module handles spawning 52 parallel simulations (1 national + 51 states)
and aggregating the results into a single response with congressional district breakdowns.
"""

import logging
from typing import Any, Callable

logger = logging.getLogger(__name__)

# Test subset: 10 diverse states (mix of populous and small)
# Populous: TX, NY, FL
# Medium: OH, GA, MA, NV
# Small: NH, VT, MT
TEST_STATE_CODES = [
    "NV",  # Medium - 4 districts
    "TX",  # Large - 38 districts
    "NY",  # Large - 26 districts
    "FL",  # Large - 28 districts
    "OH",  # Medium - 15 districts
    "GA",  # Medium - 14 districts
    "MA",  # Medium - 9 districts
    "NH",  # Small - 2 districts
    "VT",  # Small - 1 district
    "MT",  # Small - 2 districts
]

# All 50 US states + DC (51 total)
STATE_CODES = [
    "AL",
    "AK",
    "AZ",
    "AR",
    "CA",
    "CO",
    "CT",
    "DE",
    "DC",
    "FL",
    "GA",
    "HI",
    "ID",
    "IL",
    "IN",
    "IA",
    "KS",
    "KY",
    "LA",
    "ME",
    "MD",
    "MA",
    "MI",
    "MN",
    "MS",
    "MO",
    "MT",
    "NE",
    "NV",
    "NH",
    "NJ",
    "NM",
    "NY",
    "NC",
    "ND",
    "OH",
    "OK",
    "OR",
    "PA",
    "RI",
    "SC",
    "SD",
    "TN",
    "TX",
    "UT",
    "VT",
    "VA",
    "WA",
    "WV",
    "WI",
    "WY",
]


def run_national_orchestration(
    params: dict,
    run_simulation: Callable,
    state_codes: list[str] | None = None,
) -> dict:
    """
    Orchestrate parallel simulations and aggregate results.

    Spawns:
    - 1 national ECPS simulation (region="us")
    - State-level simulations for each state in state_codes (or all 51 if not specified)

    Each spawned job runs in its own container via run_simulation.

    Partial failure handling:
    - If ALL states fail, the entire request fails
    - If SOME states fail, the request succeeds with null values for failed states

    Args:
        params: Base simulation parameters (reform, baseline, time_period, etc.)
        run_simulation: The Modal function to spawn for each simulation
        state_codes: Optional list of state codes to run. If None, runs all 51.

    Returns:
        Aggregated result with national metrics + all congressional district breakdowns
    """
    states_to_run = state_codes if state_codes is not None else STATE_CODES

    # Prepare base params (remove the special data flag)
    base_params = {k: v for k, v in params.items() if k != "data"}

    # 1. Spawn national ECPS simulation
    logger.info("Spawning national ECPS simulation")
    national_params = {
        **base_params,
        "region": "us",
        # data=None lets policyengine use default ECPS dataset
    }
    national_call = run_simulation.spawn(national_params)

    # 2. Spawn state simulations (each gets its own container)
    logger.info(f"Spawning {len(states_to_run)} state-level simulations")
    state_calls: dict[str, Any] = {}
    for state_code in states_to_run:
        state_params = {
            **base_params,
            "region": f"state/{state_code.lower()}",
            # data=None lets get_default_dataset resolve to states/{CODE}.h5
        }
        state_calls[state_code] = run_simulation.spawn(state_params)

    logger.info(
        f"All {len(states_to_run) + 1} simulations spawned, waiting for results"
    )

    # 3. Wait for national result first
    logger.info("Waiting for national ECPS result")
    national_result = national_call.get()
    logger.info("National ECPS simulation complete")

    # 4. Wait for all state results and extract district data
    all_districts: list[dict] = []
    failed_states: list[str] = []
    successful_states: list[str] = []

    for state_code in states_to_run:
        logger.info(f"Waiting for {state_code} result")
        call = state_calls[state_code]

        try:
            state_result = call.get()

            # Extract congressional_district_impact.districts from state result
            district_impact = state_result.get("congressional_district_impact", {})
            districts = district_impact.get("districts", [])
            logger.info(f"{state_code}: {len(districts)} districts extracted")
            all_districts.extend(districts)
            successful_states.append(state_code)

        except Exception as e:
            logger.warning(f"{state_code}: FAILED - {str(e)[:200]}")
            failed_states.append(state_code)
            # Add null placeholder for each district in this state
            # We don't know how many districts, so we skip adding placeholders
            # The response will simply be missing these districts

    logger.info(
        f"State simulations complete. "
        f"Successful: {len(successful_states)}, Failed: {len(failed_states)}"
    )

    # 5. Check if ALL states failed
    if len(failed_states) == len(states_to_run):
        raise RuntimeError(
            f"All {len(states_to_run)} state simulations failed. "
            f"Failed states: {failed_states}"
        )

    if failed_states:
        logger.warning(f"Failed states: {failed_states}")

    logger.info(f"Total districts collected: {len(all_districts)}")

    # 6. Merge: national result + aggregated districts + metadata
    final_result = national_result.copy()
    final_result["congressional_district_impact"] = {
        "districts": all_districts,
        "failed_states": failed_states if failed_states else None,
        "successful_states": successful_states,
    }

    return final_result
