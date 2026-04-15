from __future__ import annotations

from contextlib import AbstractContextManager
from typing import Any, Callable, Mapping, TypeVar

from src.modal.gateway.models import SimulationRequest
from src.modal.observability import (
    build_lifecycle_event,
    build_metric_attributes,
    build_span_attributes,
    observe_stage,
)

T = TypeVar("T")


class _RequestSpan(AbstractContextManager["_RequestSpan"]):
    def __init__(self, observation: "GatewayObservation", name: str):
        self.observation = observation
        self.name = name
        self._span_context = None

    def __enter__(self):
        self._span_context = self.observation.observability.span(
            self.name,
            self.observation.span_attributes(country=self.observation.country),
            parent_traceparent=self.observation.current_traceparent(),
        )
        span = self._span_context.__enter__()
        self.observation.update_telemetry(traceparent=span.get_traceparent())
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        if self._span_context is None:
            return None
        return self._span_context.__exit__(exc_type, exc_value, traceback)


class GatewayObservation:
    def __init__(
        self,
        observability: Any,
        *,
        service: str,
        telemetry: dict[str, Any] | None = None,
        country: str | None = None,
    ):
        self.observability = observability
        self.service = service
        self.telemetry = telemetry
        self.country = country

    @classmethod
    def from_request(
        cls,
        observability: Any,
        request: SimulationRequest | None = None,
        telemetry: dict[str, Any] | None = None,
        service: str = "policyengine-simulation-gateway",
    ) -> "GatewayObservation":
        if telemetry is None and request is not None and request.telemetry is not None:
            telemetry = request.telemetry.model_dump(mode="json")
        return cls(
            observability,
            service=service,
            telemetry=telemetry,
            country=None if request is None else request.country,
        )

    @property
    def run_id(self) -> str | None:
        return None if self.telemetry is None else self.telemetry.get("run_id")

    def update_telemetry(self, **fields: Any) -> None:
        values = {key: value for key, value in fields.items() if value is not None}
        if not values:
            return
        if self.telemetry is None:
            self.telemetry = {}
        self.telemetry.update(values)

    def current_traceparent(self) -> str | None:
        return None if self.telemetry is None else self.telemetry.get("traceparent")

    def request_span(self, name: str) -> AbstractContextManager:
        return _RequestSpan(self, name)

    def metric_attributes(
        self,
        telemetry: Mapping[str, Any] | None = None,
        **extra: Any,
    ) -> dict[str, Any]:
        return build_metric_attributes(
            self.telemetry if telemetry is None else telemetry,
            service=self.service,
            **extra,
        )

    def span_attributes(
        self,
        telemetry: Mapping[str, Any] | None = None,
        **extra: Any,
    ) -> dict[str, Any]:
        return build_span_attributes(
            self.telemetry if telemetry is None else telemetry,
            service=self.service,
            **extra,
        )

    def emit(
        self,
        *,
        stage: str,
        status: str,
        duration_seconds: float | None = None,
        details: Mapping[str, Any] | None = None,
        **extra: Any,
    ) -> None:
        self.observability.emit_lifecycle_event(
            build_lifecycle_event(
                stage=stage,
                status=status,
                service=self.service,
                telemetry=self.telemetry,
                duration_seconds=duration_seconds,
                details=details,
                country=self.country,
                **extra,
            )
        )

    def counter(
        self,
        name: str,
        *,
        attributes: Mapping[str, Any] | None = None,
        value: int = 1,
    ) -> None:
        self.observability.emit_counter(name, value=value, attributes=attributes)

    def histogram(
        self,
        name: str,
        value: float,
        *,
        attributes: Mapping[str, Any] | None = None,
    ) -> None:
        self.observability.emit_histogram(name, value, attributes=attributes)

    def stage(
        self,
        stage: str,
        *,
        success_status: str = "ok",
        record_failure_counter: bool = False,
        details: Mapping[str, Any] | None = None,
    ) -> AbstractContextManager:
        return observe_stage(
            self.observability,
            stage=stage,
            service=self.service,
            telemetry=self.telemetry,
            success_status=success_status,
            record_failure_counter=record_failure_counter,
            details=details,
            parent_traceparent=self.current_traceparent(),
        )

    def call_stage(
        self,
        stage: str,
        fn: Callable[[], T],
        *,
        success_status: str = "ok",
        record_failure_counter: bool = False,
        details: Mapping[str, Any] | None = None,
        on_success: Callable[[T, dict[str, Any]], None] | None = None,
    ) -> T:
        with self.stage(
            stage,
            success_status=success_status,
            record_failure_counter=record_failure_counter,
            details=details,
        ) as observation:
            result = fn()
            if on_success is not None:
                on_success(result, observation.details)
            return result
