from __future__ import annotations

from types import SimpleNamespace

import pytest

from src.modal.simulation import run_simulation_impl


class RecordingSpan:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        return None

    def set_attribute(self, key, value):
        return None

    def add_event(self, name, attributes=None):
        return None


class RecordingObservability:
    def __init__(self, *, capture_mode: str):
        self.config = SimpleNamespace(
            tracer_capture_mode=capture_mode,
            artifact_bucket="diagnostics-bucket",
            artifact_prefix="simulation-observability",
            slow_run_threshold_seconds=30.0,
            tracer_success_sample_rate=0.0,
            tracer_include_computation_log=False,
        )
        self.events = []
        self.histograms = []

    def emit_lifecycle_event(self, payload):
        self.events.append(payload)

    def emit_counter(self, name, value=1, attributes=None):
        return None

    def emit_histogram(self, name, value, attributes=None):
        self.histograms.append((name, value, dict(attributes or {})))

    def span(self, name, attributes=None, parent_traceparent=None):
        return RecordingSpan()

    def record_artifact_manifest(self, manifest):
        return None


class FakeOptions:
    @classmethod
    def model_validate(cls, payload):
        return cls(payload)

    def __init__(self, payload):
        self.payload = payload

    def model_dump(self):
        return dict(self.payload)


class FakeResult:
    def model_dump(self, mode="python"):
        return {"ok": True, "mode": mode}


def test_run_simulation_impl__passes_trace_flag_and_exports_diagnostics(monkeypatch):
    created_kwargs = {}
    export_calls = []

    class FakeSimulation:
        def __init__(self, **kwargs):
            created_kwargs.update(kwargs)
            self.kwargs = kwargs
            self.tracer = object()

        def calculate_economy_comparison(self):
            return FakeResult()

    monkeypatch.setattr("src.modal.simulation.setup_gcp_credentials", lambda: None)
    monkeypatch.setattr("src.modal.simulation.SimulationOptions", FakeOptions)
    monkeypatch.setattr("src.modal.simulation.Simulation", FakeSimulation)
    monkeypatch.setattr("src.modal.simulation.build_artifact_store", lambda *args, **kwargs: object())

    def fake_export(**kwargs):
        export_calls.append(kwargs)
        return [], {"capture_reason": "slow_run"}

    monkeypatch.setattr("src.modal.simulation.export_tracer_diagnostics", fake_export)

    result = run_simulation_impl(
        {
            "country": "us",
            "_telemetry": {
                "run_id": "run-123",
                "capture_mode": "disabled",
            },
        },
        observability=RecordingObservability(capture_mode="threshold"),
    )

    assert created_kwargs["trace"] is True
    assert export_calls[0]["capture_mode"] == "threshold"
    assert export_calls[0]["failed"] is False
    assert result == {"ok": True, "mode": "json"}


def test_run_simulation_impl__exports_diagnostics_on_failure(monkeypatch):
    export_calls = []

    class FailingSimulation:
        def __init__(self, **kwargs):
            self.tracer = object()

        def calculate_economy_comparison(self):
            raise RuntimeError("boom")

    monkeypatch.setattr("src.modal.simulation.setup_gcp_credentials", lambda: None)
    monkeypatch.setattr("src.modal.simulation.SimulationOptions", FakeOptions)
    monkeypatch.setattr("src.modal.simulation.Simulation", FailingSimulation)
    monkeypatch.setattr("src.modal.simulation.build_artifact_store", lambda *args, **kwargs: object())
    monkeypatch.setattr(
        "src.modal.simulation.export_tracer_diagnostics",
        lambda **kwargs: export_calls.append(kwargs) or ([], {"capture_reason": "failed_run"}),
    )

    with pytest.raises(RuntimeError, match="boom"):
        run_simulation_impl(
            {
                "country": "us",
                "_telemetry": {
                    "run_id": "run-123",
                    "capture_mode": "always",
                },
            },
            observability=RecordingObservability(capture_mode="disabled"),
        )

    assert export_calls[0]["failed"] is True
    assert export_calls[0]["capture_mode"] == "always"
