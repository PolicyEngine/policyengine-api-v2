"""Scheduler for budget-window child simulation batches."""

from __future__ import annotations

import time
from typing import Any

import modal

from src.modal.budget_window_context import (
    BudgetWindowBatchContext,
    ChildSimulationHandle,
    build_child_simulation_request,
)
from src.modal.budget_window_results import (
    build_budget_window_result,
    extract_annual_impact,
)
from src.modal.budget_window_state import (
    build_batch_status_response,
    create_initial_batch_state,
    get_batch_job_seed,
    mark_batch_complete,
    mark_batch_failed,
    mark_batch_running,
    mark_child_completed,
    mark_child_failed,
    mark_child_started,
    put_batch_job_seed,
    put_batch_job_state,
)

# Fixed parent sweep cadence. The parent only checks child FunctionCall
# readiness; the actual compute stays in separate Modal containers. A simple
# fixed interval is easier to reason about than exponential backoff here, and
# with the budget-window flow designed to fan out many children over time we do
# not want one quick completion to reset the parent into hot polling.
POLL_INTERVAL_SECONDS = 2.0


def serialize_batch_status(state) -> dict[str, Any]:
    return build_batch_status_response(state).model_dump(mode="json")


def load_or_create_batch_state(context: BudgetWindowBatchContext):
    state = get_batch_job_seed(context.batch_job_id)
    if state is None:
        state = create_initial_batch_state(
            batch_job_id=context.batch_job_id,
            request=context.request,
            resolved_version=context.resolved_version,
            resolved_app_name=context.resolved_app_name,
            bundle=context.bundle,
        )
        put_batch_job_seed(state)
    return state


class BudgetWindowBatchRunner:
    """Runs a parent budget-window batch job to completion."""

    def __init__(
        self,
        context: BudgetWindowBatchContext,
        *,
        modal_module=None,
        poll_interval_seconds: float = POLL_INTERVAL_SECONDS,
    ):
        self.context = context
        self.modal = modal if modal_module is None else modal_module
        self.poll_interval_seconds = poll_interval_seconds
        self.state = load_or_create_batch_state(context)
        self.child_func = self.modal.Function.from_name(
            context.resolved_app_name,
            "run_simulation",
        )
        self.child_handles: dict[str, ChildSimulationHandle] = {}

    def run(self) -> dict[str, Any]:
        mark_batch_running(self.state)
        put_batch_job_state(self.state)

        while self.has_pending_work():
            self.spawn_until_capacity()
            progress_made = self.poll_running_children_once()
            if self.state.status == "failed":
                return serialize_batch_status(self.state)
            if self.state.running_years and not progress_made:
                time.sleep(self.poll_interval_seconds)

        return self.complete_batch()

    def has_pending_work(self) -> bool:
        return bool(self.state.queued_years or self.state.running_years)

    def spawn_until_capacity(self) -> None:
        while (
            len(self.state.running_years) < self.state.max_parallel
            and self.state.queued_years
        ):
            simulation_year = self.state.queued_years[0]
            child_request = build_child_simulation_request(
                self.context,
                simulation_year=simulation_year,
            )
            call = self.child_func.spawn(child_request.payload)
            self.child_handles[simulation_year] = ChildSimulationHandle(
                simulation_year=simulation_year,
                job_id=call.object_id,
                call=call,
            )
            mark_child_started(
                self.state,
                year=simulation_year,
                child_job_id=call.object_id,
            )
            put_batch_job_state(self.state)

    def poll_running_children_once(self) -> bool:
        progress_made = False

        for simulation_year in list(self.state.running_years):
            handle = self.resolve_child_handle(simulation_year)

            try:
                child_result = handle.call.get(timeout=0)
            except TimeoutError:
                continue
            except Exception as exc:
                self.fail_batch_for_child_error(
                    simulation_year=simulation_year,
                    error=str(exc),
                )
                return False

            try:
                annual_impact = extract_annual_impact(
                    simulation_year=simulation_year,
                    child_result=child_result,
                )
            except Exception as exc:
                self.fail_batch_for_child_error(
                    simulation_year=simulation_year,
                    error=str(exc),
                )
                return False

            mark_child_completed(
                self.state,
                year=simulation_year,
                annual_impact=annual_impact,
            )
            put_batch_job_state(self.state)
            progress_made = True

        return progress_made

    def resolve_child_handle(self, simulation_year: str) -> ChildSimulationHandle:
        handle = self.child_handles.get(simulation_year)
        if handle is not None and handle.call is not None:
            return handle

        job_id = self.state.child_jobs[simulation_year].job_id
        call = self.modal.FunctionCall.from_id(job_id)
        resolved_handle = ChildSimulationHandle(
            simulation_year=simulation_year,
            job_id=job_id,
            call=call,
        )
        self.child_handles[simulation_year] = resolved_handle
        return resolved_handle

    def fail_batch_for_child_error(
        self,
        *,
        simulation_year: str,
        error: str,
    ) -> None:
        mark_child_failed(self.state, year=simulation_year, error=error)
        mark_batch_failed(self.state, error=error)
        put_batch_job_state(self.state)

    def complete_batch(self) -> dict[str, Any]:
        annual_impacts = [
            self.state.partial_annual_impacts[simulation_year]
            for simulation_year in self.state.years
            if simulation_year in self.state.partial_annual_impacts
        ]
        result = build_budget_window_result(
            start_year=self.state.start_year,
            window_size=self.state.window_size,
            annual_impacts=annual_impacts,
        )
        mark_batch_complete(self.state, result=result)
        put_batch_job_state(self.state)
        return serialize_batch_status(self.state)
