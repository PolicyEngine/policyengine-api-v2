from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
import random
from typing import Any, Callable, Iterable, Mapping

from policyengine_fastapi.observability import TracerArtifactManifest

from src.modal.artifact_store import ArtifactStore
from src.modal.observability import build_metric_attributes

TRACER_ARTIFACT_FORMAT = "policyengine.tracer.bundle.v1"
TRACER_NODE_COUNT_METRIC_NAME = "policyengine.simulation.tracer.node_count"
TRACER_MAX_DEPTH_METRIC_NAME = "policyengine.simulation.tracer.max_depth"
TRACER_TOTAL_CALCULATION_TIME_METRIC_NAME = (
    "policyengine.simulation.tracer.total_calculation_time.seconds"
)
TRACER_TOTAL_FORMULA_TIME_METRIC_NAME = (
    "policyengine.simulation.tracer.total_formula_time.seconds"
)


@dataclass(frozen=True)
class TracerPersistenceDecision:
    should_persist: bool
    reason: str


@dataclass(frozen=True)
class TracerSummary:
    branch_names: tuple[str, ...]
    node_count: int
    root_count: int
    max_depth: int
    total_calculation_time_seconds: float
    total_formula_time_seconds: float


@dataclass(frozen=True)
class TracerScenarioCapture:
    scenario: str
    summary: TracerSummary
    flat_trace: dict[str, Any]
    performance_summary: dict[str, Any]
    computation_log: list[str] | None = None


def should_trace_simulation(capture_mode: str | None) -> bool:
    return (capture_mode or "disabled") != "disabled"


def resolve_capture_mode(
    telemetry_capture_mode: str | None,
    configured_capture_mode: str | None,
) -> str:
    if telemetry_capture_mode and telemetry_capture_mode != "disabled":
        return telemetry_capture_mode
    return configured_capture_mode or telemetry_capture_mode or "disabled"


def decide_tracer_artifact_persistence(
    *,
    capture_mode: str,
    failed: bool,
    run_duration_seconds: float | None,
    slow_run_threshold_seconds: float,
    success_sample_rate: float,
    random_value: float | None = None,
) -> TracerPersistenceDecision:
    normalized_mode = capture_mode or "disabled"
    if normalized_mode == "disabled":
        return TracerPersistenceDecision(False, "disabled")

    if failed:
        return TracerPersistenceDecision(True, "failed_run")

    if normalized_mode == "always":
        return TracerPersistenceDecision(True, "always")

    sampled = False
    if success_sample_rate > 0:
        sampled = (random_value or random.random()) < success_sample_rate

    if normalized_mode == "sampled":
        return TracerPersistenceDecision(sampled, "sampled_success")

    over_threshold = (
        run_duration_seconds is not None
        and run_duration_seconds >= slow_run_threshold_seconds
    )
    if normalized_mode == "threshold":
        if over_threshold:
            return TracerPersistenceDecision(True, "slow_run")
        if sampled:
            return TracerPersistenceDecision(True, "sampled_success")
        return TracerPersistenceDecision(False, "success_below_threshold")

    if normalized_mode == "failures":
        return TracerPersistenceDecision(False, "success_skipped")

    return TracerPersistenceDecision(False, "unsupported_mode")


def capture_tracer_scenarios(
    simulation: Any,
    *,
    include_computation_log: bool = False,
) -> list[TracerScenarioCapture]:
    tracer = getattr(simulation, "tracer", None)
    if tracer is None or not hasattr(tracer, "browse_trace"):
        return []

    nodes = list(tracer.browse_trace())
    if not nodes:
        return []

    serialized_flat_trace = tracer.get_serialized_flat_trace()
    raw_flat_trace = tracer.get_flat_trace()
    computation_log_lines = (
        list(tracer.computation_log.lines()) if include_computation_log else None
    )
    nodes_by_key = {_node_key(node): node for node in nodes}
    scenarios: list[TracerScenarioCapture] = []
    for scenario_name, branch_names in _scenario_branch_groups(nodes):
        branch_name_set = set(branch_names)
        scenario_keys = [
            key
            for key, node in nodes_by_key.items()
            if getattr(node, "branch_name", "default") in branch_name_set
        ]
        if not scenario_keys:
            continue

        scenario_nodes = [nodes_by_key[key] for key in scenario_keys]
        scenario_roots = [
            root
            for root in getattr(tracer, "trees", [])
            if getattr(root, "branch_name", "default") in branch_name_set
        ]
        filtered_raw_trace = {
            key: raw_flat_trace[key] for key in scenario_keys if key in raw_flat_trace
        }
        filtered_serialized_trace = {
            key: serialized_flat_trace[key]
            for key in scenario_keys
            if key in serialized_flat_trace
        }
        performance_summary = tracer.performance_log.aggregate_calculation_times(
            filtered_raw_trace
        )
        scenario_computation_log = None
        if computation_log_lines is not None:
            scenario_computation_log = [
                line
                for line in computation_log_lines
                if any(f"({branch_name})>" in line for branch_name in branch_name_set)
            ]

        scenarios.append(
            TracerScenarioCapture(
                scenario=scenario_name,
                summary=TracerSummary(
                    branch_names=tuple(branch_names),
                    node_count=len(scenario_nodes),
                    root_count=len(scenario_roots),
                    max_depth=_max_depth(scenario_roots),
                    total_calculation_time_seconds=round(
                        sum(_calculation_time(node) for node in scenario_nodes),
                        6,
                    ),
                    total_formula_time_seconds=round(
                        sum(_formula_time(node) for node in scenario_nodes),
                        6,
                    ),
                ),
                flat_trace=filtered_serialized_trace,
                performance_summary=performance_summary,
                computation_log=scenario_computation_log,
            )
        )

    return scenarios


def emit_tracer_summary_metrics(
    observability: Any,
    *,
    telemetry: Mapping[str, Any] | None,
    capture: TracerScenarioCapture,
    service: str,
) -> None:
    attributes = build_metric_attributes(
        telemetry,
        service=service,
        scenario=capture.scenario,
    )
    observability.emit_histogram(
        TRACER_NODE_COUNT_METRIC_NAME,
        float(capture.summary.node_count),
        attributes=attributes,
    )
    observability.emit_histogram(
        TRACER_MAX_DEPTH_METRIC_NAME,
        float(capture.summary.max_depth),
        attributes=attributes,
    )
    observability.emit_histogram(
        TRACER_TOTAL_CALCULATION_TIME_METRIC_NAME,
        capture.summary.total_calculation_time_seconds,
        attributes=attributes,
    )
    observability.emit_histogram(
        TRACER_TOTAL_FORMULA_TIME_METRIC_NAME,
        capture.summary.total_formula_time_seconds,
        attributes=attributes,
    )


def persist_tracer_artifacts(
    *,
    artifact_store: ArtifactStore,
    captures: Iterable[TracerScenarioCapture],
    telemetry: Mapping[str, Any] | None,
    capture_mode: str,
    clock: Callable[[], datetime] | None = None,
) -> list[TracerArtifactManifest]:
    timestamp = (clock or (lambda: datetime.now(UTC)))()
    manifests: list[TracerArtifactManifest] = []
    run_id = str(None if telemetry is None else telemetry.get("run_id") or "unknown")
    country = None if telemetry is None else telemetry.get("country")
    country_package_version = (
        None if telemetry is None else telemetry.get("country_package_version")
    )

    for capture in captures:
        flat_trace_artifact = artifact_store.put_json(
            artifact_store.build_object_name(
                run_id=run_id,
                scenario=capture.scenario,
                artifact_name="flat_trace",
                extension="json",
                country=country,
                country_package_version=country_package_version,
            ),
            capture.flat_trace,
        )
        performance_artifact = artifact_store.put_json(
            artifact_store.build_object_name(
                run_id=run_id,
                scenario=capture.scenario,
                artifact_name="performance_summary",
                extension="json",
                country=country,
                country_package_version=country_package_version,
            ),
            capture.performance_summary,
        )
        artifacts = {
            "flat_trace": flat_trace_artifact.storage_uri,
            "performance_summary": performance_artifact.storage_uri,
        }
        if capture.computation_log is not None:
            computation_artifact = artifact_store.put_text(
                artifact_store.build_object_name(
                    run_id=run_id,
                    scenario=capture.scenario,
                    artifact_name="computation_log",
                    extension="txt",
                    country=country,
                    country_package_version=country_package_version,
                ),
                "\n".join(capture.computation_log),
            )
            artifacts["computation_log"] = computation_artifact.storage_uri

        manifests.append(
            TracerArtifactManifest(
                run_id=run_id,
                process_id=None if telemetry is None else telemetry.get("process_id"),
                request_id=None if telemetry is None else telemetry.get("request_id"),
                country=country,
                simulation_kind=(
                    None if telemetry is None else telemetry.get("simulation_kind")
                ),
                geography_code=(
                    None if telemetry is None else telemetry.get("geography_code")
                ),
                geography_type=(
                    None if telemetry is None else telemetry.get("geography_type")
                ),
                country_package_name=(
                    None
                    if telemetry is None
                    else telemetry.get("country_package_name")
                ),
                country_package_version=country_package_version,
                policyengine_version=(
                    None if telemetry is None else telemetry.get("policyengine_version")
                ),
                modal_app_name=(
                    None if telemetry is None else telemetry.get("modal_app_name")
                ),
                config_hash=None if telemetry is None else telemetry.get("config_hash"),
                scenario=capture.scenario,
                capture_mode=capture_mode,
                artifact_format=TRACER_ARTIFACT_FORMAT,
                storage_uri=flat_trace_artifact.storage_uri,
                summary_uri=performance_artifact.storage_uri,
                branch_names=list(capture.summary.branch_names),
                artifacts=artifacts,
                node_count=capture.summary.node_count,
                root_count=capture.summary.root_count,
                max_depth=capture.summary.max_depth,
                total_calculation_time_seconds=(
                    capture.summary.total_calculation_time_seconds
                ),
                total_formula_time_seconds=(
                    capture.summary.total_formula_time_seconds
                ),
                generated_at=timestamp,
            )
        )

    return manifests


def export_tracer_diagnostics(
    *,
    simulation: Any,
    observability: Any,
    telemetry: Mapping[str, Any] | None,
    service: str,
    capture_mode: str,
    run_duration_seconds: float | None,
    failed: bool,
    artifact_store: ArtifactStore | None,
    slow_run_threshold_seconds: float,
    success_sample_rate: float,
    include_computation_log: bool,
    random_value: float | None = None,
    clock: Callable[[], datetime] | None = None,
) -> tuple[list[TracerArtifactManifest], dict[str, Any]]:
    decision = decide_tracer_artifact_persistence(
        capture_mode=capture_mode,
        failed=failed,
        run_duration_seconds=run_duration_seconds,
        slow_run_threshold_seconds=slow_run_threshold_seconds,
        success_sample_rate=success_sample_rate,
        random_value=random_value,
    )
    captures = capture_tracer_scenarios(
        simulation,
        include_computation_log=(
            include_computation_log and decision.should_persist
        ),
    )
    for capture in captures:
        emit_tracer_summary_metrics(
            observability,
            telemetry=telemetry,
            capture=capture,
            service=service,
        )

    manifests: list[TracerArtifactManifest] = []
    if decision.should_persist and artifact_store is not None:
        manifests = persist_tracer_artifacts(
            artifact_store=artifact_store,
            captures=captures,
            telemetry=telemetry,
            capture_mode=capture_mode,
            clock=clock,
        )
        for manifest in manifests:
            observability.record_artifact_manifest(manifest)

    return manifests, {
        "capture_mode": capture_mode,
        "capture_reason": decision.reason,
        "persisted_artifacts": bool(manifests),
        "scenario_count": len(captures),
        "artifact_manifest_count": len(manifests),
        "tracer_node_count": sum(capture.summary.node_count for capture in captures),
    }


def _scenario_branch_groups(nodes: Iterable[Any]) -> list[tuple[str, tuple[str, ...]]]:
    branch_names = sorted(
        {getattr(node, "branch_name", "default") for node in nodes} or {"default"}
    )
    if "baseline" not in branch_names:
        return [("default", tuple(branch_names))]

    reform_branches = tuple(name for name in branch_names if name != "baseline")
    groups: list[tuple[str, tuple[str, ...]]] = [("baseline", ("baseline",))]
    if reform_branches:
        groups.append(("reform", reform_branches))
    return groups


def _node_key(node: Any) -> str:
    return (
        f"{getattr(node, 'name')}<"
        f"{getattr(node, 'period')}, ({getattr(node, 'branch_name', 'default')})>"
    )


def _calculation_time(node: Any) -> float:
    try:
        return float(node.calculation_time(round_=False))
    except TypeError:
        return float(node.calculation_time())


def _formula_time(node: Any) -> float:
    return float(node.formula_time())


def _max_depth(roots: Iterable[Any]) -> int:
    def _depth(node: Any, current_depth: int) -> int:
        children = getattr(node, "children", [])
        if not children:
            return current_depth
        return max(_depth(child, current_depth + 1) for child in children)

    max_depth = 0
    for root in roots:
        max_depth = max(max_depth, _depth(root, 1))
    return max_depth
