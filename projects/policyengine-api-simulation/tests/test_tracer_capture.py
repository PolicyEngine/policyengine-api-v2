from __future__ import annotations

from types import SimpleNamespace

from src.modal.tracer_capture import (
    TRACER_MAX_DEPTH_METRIC_NAME,
    TRACER_NODE_COUNT_METRIC_NAME,
    TRACER_TOTAL_CALCULATION_TIME_METRIC_NAME,
    TRACER_TOTAL_FORMULA_TIME_METRIC_NAME,
    capture_tracer_scenarios,
    decide_tracer_artifact_persistence,
    export_tracer_diagnostics,
)


class FakeNode:
    def __init__(
        self,
        name: str,
        period: str,
        *,
        branch_name: str = "default",
        calculation_time: float = 0.0,
        formula_time: float = 0.0,
        children: list["FakeNode"] | None = None,
    ):
        self.name = name
        self.period = period
        self.branch_name = branch_name
        self.children = children or []
        self.parameters = []
        self._calculation_time = calculation_time
        self._formula_time = formula_time

    def calculation_time(self, round_: bool = True) -> float:
        return self._calculation_time

    def formula_time(self) -> float:
        return self._formula_time


def _trace_key(node: FakeNode) -> str:
    return f"{node.name}<{node.period}, ({node.branch_name})>"


class FakePerformanceLog:
    def aggregate_calculation_times(self, flat_trace: dict[str, dict]) -> dict[str, dict]:
        aggregated: dict[str, dict] = {}
        for key, value in flat_trace.items():
            variable_name = key.split("<", 1)[0]
            current = aggregated.setdefault(
                variable_name,
                {
                    "calculation_count": 0,
                    "calculation_time": 0.0,
                    "formula_time": 0.0,
                },
            )
            current["calculation_count"] += 1
            current["calculation_time"] += value["calculation_time"]
            current["formula_time"] += value["formula_time"]
        return aggregated


class FakeComputationLog:
    def __init__(self, lines: list[str]):
        self._lines = lines

    def lines(self) -> list[str]:
        return list(self._lines)


class FakeTracer:
    def __init__(self, trees: list[FakeNode], lines: list[str]):
        self.trees = trees
        self.performance_log = FakePerformanceLog()
        self.computation_log = FakeComputationLog(lines)
        self._flat_trace = self._build_flat_trace()

    def browse_trace(self):
        def _visit(node: FakeNode):
            yield node
            for child in node.children:
                yield from _visit(child)

        for tree in self.trees:
            yield from _visit(tree)

    def _build_flat_trace(self) -> dict[str, dict]:
        trace = {}
        for node in self.browse_trace():
            trace[_trace_key(node)] = {
                "dependencies": [_trace_key(child) for child in node.children],
                "parameters": {},
                "value": None,
                "calculation_time": node.calculation_time(),
                "formula_time": node.formula_time(),
            }
        return trace

    def get_flat_trace(self) -> dict[str, dict]:
        return dict(self._flat_trace)

    def get_serialized_flat_trace(self) -> dict[str, dict]:
        return dict(self._flat_trace)


class FakeArtifactStore:
    bucket_name = "diagnostics"
    prefix = "simulation-observability"

    def __init__(self):
        self.uploads: list[tuple[str, object]] = []

    def build_object_name(self, **kwargs) -> str:
        return "/".join(
            [
                "simulation-observability",
                kwargs["scenario"],
                kwargs["artifact_name"],
                f'{kwargs["artifact_name"]}.{kwargs["extension"]}',
            ]
        )

    def put_json(self, object_name: str, payload):
        self.uploads.append((object_name, payload))
        return SimpleNamespace(storage_uri=f"gs://diagnostics/{object_name}")

    def put_text(self, object_name: str, payload: str):
        self.uploads.append((object_name, payload))
        return SimpleNamespace(storage_uri=f"gs://diagnostics/{object_name}")


class RecordingObservability:
    def __init__(self):
        self.histograms = []
        self.manifests = []

    def emit_histogram(self, name, value, attributes=None):
        self.histograms.append((name, value, dict(attributes or {})))

    def record_artifact_manifest(self, manifest):
        self.manifests.append(manifest)


def test_decide_tracer_artifact_persistence__captures_failures_threshold_and_sampling():
    failed = decide_tracer_artifact_persistence(
        capture_mode="failures",
        failed=True,
        run_duration_seconds=1.0,
        slow_run_threshold_seconds=30.0,
        success_sample_rate=0.0,
    )
    slow = decide_tracer_artifact_persistence(
        capture_mode="threshold",
        failed=False,
        run_duration_seconds=45.0,
        slow_run_threshold_seconds=30.0,
        success_sample_rate=0.0,
    )
    sampled = decide_tracer_artifact_persistence(
        capture_mode="threshold",
        failed=False,
        run_duration_seconds=5.0,
        slow_run_threshold_seconds=30.0,
        success_sample_rate=0.5,
        random_value=0.1,
    )

    assert failed.should_persist is True
    assert failed.reason == "failed_run"
    assert slow.reason == "slow_run"
    assert sampled.reason == "sampled_success"


def test_capture_tracer_scenarios__splits_baseline_and_reform():
    baseline_child = FakeNode(
        "baseline_child",
        "2026",
        branch_name="baseline",
        calculation_time=0.2,
        formula_time=0.1,
    )
    baseline_root = FakeNode(
        "baseline_root",
        "2026",
        branch_name="baseline",
        calculation_time=0.5,
        formula_time=0.3,
        children=[baseline_child],
    )
    reform_root = FakeNode(
        "reform_root",
        "2026",
        branch_name="default",
        calculation_time=0.8,
        formula_time=0.5,
    )
    tracer = FakeTracer(
        [baseline_root, reform_root],
        [
            "  baseline_root<2026, (baseline)> = ...",
            "    baseline_child<2026, (baseline)> = ...",
            "  reform_root<2026, (default)> = ...",
        ],
    )
    simulation = SimpleNamespace(tracer=tracer)

    captures = capture_tracer_scenarios(
        simulation,
        include_computation_log=True,
    )

    assert [capture.scenario for capture in captures] == ["baseline", "reform"]
    assert captures[0].summary.node_count == 2
    assert captures[0].summary.max_depth == 2
    assert captures[1].summary.branch_names == ("default",)
    assert captures[1].computation_log == ["  reform_root<2026, (default)> = ..."]


def test_export_tracer_diagnostics__emits_summary_metrics_and_manifests():
    baseline_root = FakeNode(
        "baseline_root",
        "2026",
        branch_name="baseline",
        calculation_time=0.5,
        formula_time=0.25,
    )
    reform_root = FakeNode(
        "reform_root",
        "2026",
        branch_name="default",
        calculation_time=0.8,
        formula_time=0.4,
    )
    simulation = SimpleNamespace(
        tracer=FakeTracer(
            [baseline_root, reform_root],
            [
                "  baseline_root<2026, (baseline)> = ...",
                "  reform_root<2026, (default)> = ...",
            ],
        )
    )
    observability = RecordingObservability()
    artifact_store = FakeArtifactStore()

    manifests, details = export_tracer_diagnostics(
        simulation=simulation,
        observability=observability,
        telemetry={
            "run_id": "run-123",
            "country": "us",
            "simulation_kind": "state",
            "country_package_version": "1.632.5",
        },
        service="policyengine-simulation-worker",
        capture_mode="threshold",
        run_duration_seconds=45.0,
        failed=False,
        artifact_store=artifact_store,
        slow_run_threshold_seconds=30.0,
        success_sample_rate=0.0,
        include_computation_log=True,
    )

    histogram_names = {name for name, _, _ in observability.histograms}
    assert histogram_names == {
        TRACER_NODE_COUNT_METRIC_NAME,
        TRACER_MAX_DEPTH_METRIC_NAME,
        TRACER_TOTAL_CALCULATION_TIME_METRIC_NAME,
        TRACER_TOTAL_FORMULA_TIME_METRIC_NAME,
    }
    assert len(manifests) == 2
    assert len(observability.manifests) == 2
    assert details["capture_reason"] == "slow_run"
    assert details["persisted_artifacts"] is True
    assert any("computation_log.txt" in object_name for object_name, _ in artifact_store.uploads)
