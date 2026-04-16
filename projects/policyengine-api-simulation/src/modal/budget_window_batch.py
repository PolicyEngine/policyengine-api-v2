"""Thin entrypoint for budget-window batch execution."""

from __future__ import annotations

from typing import Any

import modal

from src.modal.budget_window_context import build_batch_context
from src.modal.budget_window_scheduler import BudgetWindowBatchRunner


def run_budget_window_batch_impl(params: dict[str, Any]) -> dict[str, Any]:
    context = build_batch_context(
        params,
        batch_job_id=modal.current_function_call_id(),
    )
    runner = BudgetWindowBatchRunner(context)
    return runner.run()
