"""
Simulation-specific observability helpers built on the shared OTLP runtime.
"""

from __future__ import annotations

from contextlib import AbstractContextManager
from datetime import UTC, datetime
from time import perf_counter
from typing import Any, Mapping

from policyengine_fastapi.observability import (
    ObservabilityConfig,
    build_observability as build_shared_observability,
    build_traceparent as shared_build_traceparent,
    parse_bool,
    parse_header_value_pairs,
)

__all__ = [
    "FAILURE_COUNT_METRIC_NAME",
    "LOW_CARDINALITY_METRIC_KEYS",
    "QUEUE_DURATION_METRIC_NAME",
    "SPAN_ATTRIBUTE_KEYS",
    "STAGE_DURATION_METRIC_NAME",
    "StageObservation",
    "build_lifecycle_event",
    "build_metric_attributes",
    "build_span_attributes",
    "build_traceparent",
    "duration_since_requested_at",
    "get_observability",
    "observe_stage",
    "parse_bool",
    "parse_header_value_pairs",
]

LOW_CARDINALITY_METRIC_KEYS = (
    "country",
    "simulation_kind",
    "country_package_version",
    "policyengine_version",
    "capture_mode",
)
SPAN_ATTRIBUTE_KEYS = (
    "run_id",
    "process_id",
    "request_id",
    "country",
    "simulation_kind",
    "geography_type",
    "geography_code",
    "country_package_name",
    "country_package_version",
    "policyengine_version",
    "data_version",
    "modal_app_name",
    "config_hash",
    "capture_mode",
)
STAGE_DURATION_METRIC_NAME = "policyengine.simulation.stage.duration.seconds"
QUEUE_DURATION_METRIC_NAME = "policyengine.simulation.queue.duration.seconds"
FAILURE_COUNT_METRIC_NAME = "policyengine.simulation.failure.count"


def build_metric_attributes(
    telemetry: Mapping[str, Any] | None = None,
    **extra: Any,
) -> dict[str, Any]:
    attributes: dict[str, Any] = {}
    if telemetry:
        for key in LOW_CARDINALITY_METRIC_KEYS:
            value = telemetry.get(key)
            if value is not None:
                attributes[key] = value
    attributes.update({k: v for k, v in extra.items() if v is not None})
    return attributes


def build_span_attributes(
    telemetry: Mapping[str, Any] | None = None,
    **extra: Any,
) -> dict[str, Any]:
    attributes: dict[str, Any] = {}
    if telemetry:
        for key in SPAN_ATTRIBUTE_KEYS:
            value = telemetry.get(key)
            if value is not None:
                attributes[key] = value
    attributes.update({k: v for k, v in extra.items() if v is not None})
    return attributes


def build_traceparent(span_context: Any) -> str | None:
    return shared_build_traceparent(span_context)


def build_lifecycle_event(
    *,
    stage: str,
    status: str,
    service: str,
    telemetry: Mapping[str, Any] | None = None,
    duration_seconds: float | None = None,
    details: Mapping[str, Any] | None = None,
    **extra: Any,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "event_name": "simulation.lifecycle",
        "stage": stage,
        "status": status,
        "timestamp": datetime.now(UTC).isoformat(),
        "service": service,
        "details": dict(details or {}),
    }
    if duration_seconds is not None:
        payload["duration_seconds"] = duration_seconds
    if telemetry:
        payload.update({k: v for k, v in telemetry.items() if v is not None})
    payload.update({k: v for k, v in extra.items() if v is not None})
    return payload


def duration_since_requested_at(
    telemetry: Mapping[str, Any] | None,
) -> float | None:
    requested_at = None if telemetry is None else telemetry.get("requested_at")
    if not requested_at:
        return None
    try:
        requested = datetime.fromisoformat(str(requested_at))
    except ValueError:
        return None
    return (datetime.now(UTC) - requested.astimezone(UTC)).total_seconds()


class StageObservation(AbstractContextManager["StageObservation"]):
    def __init__(
        self,
        observability: Any,
        *,
        stage: str,
        service: str,
        telemetry: Mapping[str, Any] | None = None,
        success_status: str = "ok",
        record_failure_counter: bool = False,
        details: Mapping[str, Any] | None = None,
        parent_traceparent: str | None = None,
        timer=perf_counter,
    ):
        self.observability = observability
        self.stage = stage
        self.service = service
        self.telemetry = telemetry
        self.success_status = success_status
        self.record_failure_counter = record_failure_counter
        self.details: dict[str, Any] = dict(details or {})
        self.parent_traceparent = parent_traceparent
        self.timer = timer
        self._start = 0.0
        self._span_context = None
        self.span = None

    def __enter__(self):
        self._start = self.timer()
        self._span_context = self.observability.span(
            self.stage,
            build_span_attributes(
                self.telemetry,
                service=self.service,
                stage=self.stage,
            ),
            parent_traceparent=self.parent_traceparent,
        )
        self.span = self._span_context.__enter__()
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        duration = max(0.0, self.timer() - self._start)
        status = self.success_status if exc_type is None else "failed"
        if exc_value is not None and "error" not in self.details:
            self.details["error"] = str(exc_value)

        self.observability.emit_histogram(
            STAGE_DURATION_METRIC_NAME,
            duration,
            attributes=build_metric_attributes(
                self.telemetry,
                service=self.service,
                stage=self.stage,
                status=status,
            ),
        )
        if exc_type is not None and self.record_failure_counter:
            self.observability.emit_counter(
                FAILURE_COUNT_METRIC_NAME,
                attributes=build_metric_attributes(
                    self.telemetry,
                    service=self.service,
                    stage=self.stage,
                    status="failed",
                ),
            )
        self.observability.emit_lifecycle_event(
            build_lifecycle_event(
                stage=self.stage,
                status=status,
                service=self.service,
                telemetry=self.telemetry,
                duration_seconds=duration,
                details=self.details,
            )
        )
        if self._span_context is None:
            return None
        return self._span_context.__exit__(exc_type, exc_value, traceback)


def observe_stage(
    observability: Any,
    *,
    stage: str,
    service: str,
    telemetry: Mapping[str, Any] | None = None,
    success_status: str = "ok",
    record_failure_counter: bool = False,
    details: Mapping[str, Any] | None = None,
    parent_traceparent: str | None = None,
    timer=perf_counter,
) -> StageObservation:
    return StageObservation(
        observability,
        stage=stage,
        service=service,
        telemetry=telemetry,
        success_status=success_status,
        record_failure_counter=record_failure_counter,
        details=details,
        parent_traceparent=parent_traceparent,
        timer=timer,
    )


def get_observability(
    service_name: str,
    environment: str = "production",
):
    config = ObservabilityConfig.from_env(service_name, environment)
    return build_shared_observability(config)
