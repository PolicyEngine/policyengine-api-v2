"""Tests for budget-window batch orchestration."""

from __future__ import annotations

from collections import deque

import pytest

import src.modal.budget_window_batch as batch_module
import src.modal.budget_window_state as state_module
from src.modal.budget_window_batch import (
    build_budget_window_output,
    build_child_simulation_payload,
    extract_budget_window_annual_impact,
    run_budget_window_batch_impl,
    sum_budget_window_annual_impacts,
)
from src.modal.gateway.models import (
    BudgetWindowAnnualImpact,
    BudgetWindowBatchRequest,
    PolicyEngineBundle,
)


class SequencedCall:
    def __init__(self, object_id: str, events, tracker):
        self.object_id = object_id
        self._events = deque(events)
        self._tracker = tracker
        self._done = False
        self._tracker.started(self.object_id)

    def get(self, timeout: int = 0):
        event = self._events[0]
        if isinstance(event, TimeoutError):
            self._events.popleft()
            raise TimeoutError()

        self._events.popleft()
        if isinstance(event, Exception):
            self._finish()
            raise event

        self._finish()
        return event

    def _finish(self):
        if not self._done:
            self._done = True
            self._tracker.finished(self.object_id)


class SpawnTracker:
    def __init__(self):
        self.active = set()
        self.max_active = 0

    def started(self, object_id: str):
        self.active.add(object_id)
        self.max_active = max(self.max_active, len(self.active))

    def finished(self, object_id: str):
        self.active.discard(object_id)


class MockRunSimulationFunction:
    def __init__(
        self,
        *,
        tracker: SpawnTracker,
        results_by_year: dict[str, list[object]],
        call_registry: dict[str, SequencedCall],
    ):
        self.tracker = tracker
        self.results_by_year = results_by_year
        self.call_registry = call_registry
        self.spawned_years: list[str] = []

    def spawn(self, payload: dict) -> SequencedCall:
        year = payload["time_period"]
        self.spawned_years.append(year)
        call = SequencedCall(
            object_id=f"child-{year}",
            events=list(self.results_by_year[year]),
            tracker=self.tracker,
        )
        self.call_registry[call.object_id] = call
        return call


@pytest.fixture
def mock_batch_modal(monkeypatch):
    dicts: dict[str, dict] = {}
    call_registry: dict[str, SequencedCall] = {}
    functions: dict[tuple[str, str], object] = {}
    parent_call_id = "parent-123"

    class MockDict:
        def __init__(self, data: dict):
            self._data = data

        def __getitem__(self, key: str):
            return self._data[key]

        def __setitem__(self, key: str, value):
            self._data[key] = value

        def get(self, key: str, default=None):
            return self._data.get(key, default)

    class MockModalDict:
        @staticmethod
        def from_name(name: str, create_if_missing: bool = False):
            if create_if_missing and name not in dicts:
                dicts[name] = {}
            if name not in dicts:
                raise KeyError(name)
            return MockDict(dicts[name])

    class MockModalFunctionCall:
        @classmethod
        def from_id(cls, object_id: str):
            return call_registry[object_id]

    class MockModalFunction:
        @staticmethod
        def from_name(app_name: str, func_name: str):
            return functions[(app_name, func_name)]

    class MockModal:
        Dict = MockModalDict
        Function = MockModalFunction
        FunctionCall = MockModalFunctionCall

        @staticmethod
        def current_function_call_id():
            return parent_call_id

    monkeypatch.setattr(batch_module, "modal", MockModal)
    monkeypatch.setattr(state_module, "modal", MockModal)
    monkeypatch.setattr(batch_module.time, "sleep", lambda _: None)

    return {
        "dicts": dicts,
        "call_registry": call_registry,
        "functions": functions,
        "parent_call_id": parent_call_id,
    }


def _build_parent_payload(*, window_size: int = 3):
    request = BudgetWindowBatchRequest(
        country="us",
        region="us",
        start_year="2026",
        window_size=window_size,
        max_parallel=2,
        scope="macro",
        reform={},
        _telemetry={
            "run_id": "batch-run-123",
            "process_id": "proc-123",
            "capture_mode": "disabled",
        },
    )
    payload = request.model_dump(mode="json", exclude={"telemetry"})
    payload["version"] = "1.500.0"
    payload["_telemetry"] = request.telemetry.model_dump(mode="json")
    payload["_metadata"] = {
        "resolved_version": "1.500.0",
        "resolved_app_name": "policyengine-simulation-us1-500-0-uk2-66-0",
        "policyengine_bundle": PolicyEngineBundle(model_version="1.500.0").model_dump(
            mode="json"
        ),
    }
    return request, payload


def _seed_parent_batch(request: BudgetWindowBatchRequest, batch_job_id: str):
    seed = state_module.create_initial_batch_state(
        batch_job_id=batch_job_id,
        request=request,
        resolved_version="1.500.0",
        resolved_app_name="policyengine-simulation-us1-500-0-uk2-66-0",
        bundle=PolicyEngineBundle(model_version="1.500.0"),
    )
    state_module.put_batch_job_seed(seed)


def test_build_child_simulation_payload_removes_batch_only_fields():
    _, payload = _build_parent_payload()

    child_payload = build_child_simulation_payload(payload, year="2028")

    assert child_payload["time_period"] == "2028"
    assert child_payload["region"] == "us"
    assert child_payload["scope"] == "macro"
    assert "_telemetry" in child_payload
    assert "version" not in child_payload
    assert "start_year" not in child_payload
    assert "window_size" not in child_payload
    assert "max_parallel" not in child_payload
    assert "_metadata" not in child_payload


def test_extract_budget_window_annual_impact_matches_v1_shape():
    annual = extract_budget_window_annual_impact(
        year="2026",
        impact_data={
            "budget": {
                "tax_revenue_impact": 100,
                "state_tax_revenue_impact": 40,
                "benefit_spending_impact": 20,
                "budgetary_impact": 80,
            }
        },
    )

    assert annual == BudgetWindowAnnualImpact(
        year="2026",
        taxRevenueImpact=100,
        federalTaxRevenueImpact=60,
        stateTaxRevenueImpact=40,
        benefitSpendingImpact=20,
        budgetaryImpact=80,
    )


def test_build_budget_window_output_sums_totals():
    annual_impacts = [
        BudgetWindowAnnualImpact(
            year="2026",
            taxRevenueImpact=10,
            federalTaxRevenueImpact=7,
            stateTaxRevenueImpact=3,
            benefitSpendingImpact=5,
            budgetaryImpact=15,
        ),
        BudgetWindowAnnualImpact(
            year="2027",
            taxRevenueImpact=11,
            federalTaxRevenueImpact=8,
            stateTaxRevenueImpact=3,
            benefitSpendingImpact=6,
            budgetaryImpact=17,
        ),
    ]

    totals = sum_budget_window_annual_impacts(annual_impacts)
    result = build_budget_window_output(
        start_year="2026",
        window_size=2,
        annual_impacts=annual_impacts,
    )

    assert totals.budgetaryImpact == 32
    assert result.endYear == "2027"
    assert result.totals.taxRevenueImpact == 21
    assert result.totals.budgetaryImpact == 32


def test_run_budget_window_batch_impl_completes_and_respects_max_parallel(
    mock_batch_modal,
):
    request, payload = _build_parent_payload()
    _seed_parent_batch(request, mock_batch_modal["parent_call_id"])

    tracker = SpawnTracker()
    run_simulation = MockRunSimulationFunction(
        tracker=tracker,
        results_by_year={
            "2026": [
                TimeoutError(),
                {
                    "budget": {
                        "tax_revenue_impact": 10,
                        "state_tax_revenue_impact": 3,
                        "benefit_spending_impact": 5,
                        "budgetary_impact": 15,
                    }
                },
            ],
            "2027": [
                {
                    "budget": {
                        "tax_revenue_impact": 11,
                        "state_tax_revenue_impact": 3,
                        "benefit_spending_impact": 6,
                        "budgetary_impact": 17,
                    }
                }
            ],
            "2028": [
                {
                    "budget": {
                        "tax_revenue_impact": 12,
                        "state_tax_revenue_impact": 4,
                        "benefit_spending_impact": 7,
                        "budgetary_impact": 19,
                    }
                }
            ],
        },
        call_registry=mock_batch_modal["call_registry"],
    )
    mock_batch_modal["functions"][
        ("policyengine-simulation-us1-500-0-uk2-66-0", "run_simulation")
    ] = run_simulation

    result = run_budget_window_batch_impl(payload)
    state = state_module.get_batch_job_state(mock_batch_modal["parent_call_id"])

    assert tracker.max_active == 2
    assert run_simulation.spawned_years == ["2026", "2027", "2028"]
    assert result["status"] == "complete"
    assert result["progress"] == 100
    assert result["completed_years"] == ["2027", "2026", "2028"]
    assert result["result"]["annualImpacts"][0]["year"] == "2026"
    assert result["result"]["totals"]["budgetaryImpact"] == 51
    assert state is not None
    assert state.status == "complete"
    assert state.result is not None
    assert state.result.totals.budgetaryImpact == 51


def test_run_budget_window_batch_impl_marks_failure(mock_batch_modal):
    request, payload = _build_parent_payload(window_size=2)
    _seed_parent_batch(request, mock_batch_modal["parent_call_id"])

    tracker = SpawnTracker()
    run_simulation = MockRunSimulationFunction(
        tracker=tracker,
        results_by_year={
            "2026": [RuntimeError("child failed")],
            "2027": [
                {
                    "budget": {
                        "tax_revenue_impact": 11,
                        "state_tax_revenue_impact": 3,
                        "benefit_spending_impact": 6,
                        "budgetary_impact": 17,
                    }
                }
            ],
        },
        call_registry=mock_batch_modal["call_registry"],
    )
    mock_batch_modal["functions"][
        ("policyengine-simulation-us1-500-0-uk2-66-0", "run_simulation")
    ] = run_simulation

    result = run_budget_window_batch_impl(payload)
    state = state_module.get_batch_job_state(mock_batch_modal["parent_call_id"])

    assert result["status"] == "failed"
    assert result["failed_years"] == ["2026"]
    assert result["error"] == "child failed"
    assert state is not None
    assert state.status == "failed"
    assert state.error == "child failed"
