"""
Orchestration logic for national-with-breakdowns simulations.

This module handles spawning 52 parallel simulations (1 national + 51 states)
and aggregating the results into a single response with congressional district breakdowns.
"""

import logfire
from typing import Any, Callable

from src.modal.utils.state_codes import STATE_CODES, TEST_STATE_CODES

# Re-export for backwards compatibility
__all__ = ["STATE_CODES", "TEST_STATE_CODES", "run_national_orchestration"]


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
    logfire.info("Spawning national ECPS simulation")
    national_params = {
        **base_params,
        "region": "us",
        # data=None lets policyengine use default ECPS dataset
    }
    national_call = run_simulation.spawn(national_params)

    # 2. Spawn state simulations (each gets its own container)
    logfire.info("Spawning state-level simulations", state_count=len(states_to_run))
    state_calls: dict[str, Any] = {}
    for state_code in states_to_run:
        state_params = {
            **base_params,
            "region": f"state/{state_code.lower()}",
            # data=None lets get_default_dataset resolve to states/{CODE}.h5
        }
        state_calls[state_code] = run_simulation.spawn(state_params)

    logfire.info(
        "All simulations spawned, waiting for results",
        total_jobs=len(states_to_run) + 1,
    )

    # 3. Wait for national result first
    logfire.info("Waiting for national ECPS result")
    national_result = national_call.get()
    logfire.info("National ECPS simulation complete")

    # 4. Wait for all state results and extract district data
    all_districts: list[dict] = []
    failed_states: list[str] = []
    successful_states: list[str] = []

    for state_code in states_to_run:
        logfire.info("Waiting for state result", state_code=state_code)
        call = state_calls[state_code]

        try:
            state_result = call.get()

            # Extract congressional_district_impact.districts from state result
            district_impact = state_result.get("congressional_district_impact", {})
            districts = district_impact.get("districts", [])
            logfire.info(
                "State result received",
                state_code=state_code,
                districts_extracted=len(districts),
            )
            all_districts.extend(districts)
            successful_states.append(state_code)

        except Exception as e:
            logfire.warn(
                "State simulation failed",
                state_code=state_code,
                error=str(e)[:200],
            )
            failed_states.append(state_code)
            # Add null placeholder for each district in this state
            # We don't know how many districts, so we skip adding placeholders
            # The response will simply be missing these districts

    logfire.info(
        "State simulations complete",
        successful_count=len(successful_states),
        failed_count=len(failed_states),
    )

    # 5. Check if ALL states failed
    if len(failed_states) == len(states_to_run):
        raise RuntimeError(
            f"All {len(states_to_run)} state simulations failed. "
            f"Failed states: {failed_states}"
        )

    if failed_states:
        logfire.warn("Some states failed", failed_states=failed_states)

    logfire.info("Total districts collected", total_districts=len(all_districts))

    # 6. Merge: national result + aggregated districts + metadata
    final_result = national_result.copy()
    final_result["congressional_district_impact"] = {
        "districts": all_districts,
        "failed_states": failed_states if failed_states else None,
        "successful_states": successful_states,
    }

    return final_result
