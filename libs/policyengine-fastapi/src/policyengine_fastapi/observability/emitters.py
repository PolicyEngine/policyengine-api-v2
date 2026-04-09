from __future__ import annotations

from contextlib import AbstractContextManager
from dataclasses import dataclass, field
from datetime import date, datetime
from enum import Enum
import json
import logging
from typing import Protocol
from typing import Any, Mapping

from .config import ObservabilityConfig
from .contracts import SimulationLifecycleEvent, TracerArtifactManifest


class NoOpSpan(AbstractContextManager["NoOpSpan"]):
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        return None

    def set_attribute(self, key: str, value: Any) -> None:
        return None

    def add_event(
        self, name: str, attributes: Mapping[str, Any] | None = None
    ) -> None:
        return None


class OTelSpan(AbstractContextManager["OTelSpan"]):
    def __init__(self, context_manager: AbstractContextManager):
        self._context_manager = context_manager
        self._span = None

    def __enter__(self):
        self._span = self._context_manager.__enter__()
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        return self._context_manager.__exit__(exc_type, exc_value, traceback)

    def set_attribute(self, key: str, value: Any) -> None:
        if self._span is not None:
            self._span.set_attribute(key, _normalize_attribute_value(value))

    def add_event(
        self, name: str, attributes: Mapping[str, Any] | None = None
    ) -> None:
        if self._span is not None:
            self._span.add_event(name, _normalize_attributes(attributes))


class JsonPayloadFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        message = record.msg
        if isinstance(message, str):
            return message
        if isinstance(message, Mapping):
            payload = dict(message)
        else:
            payload = {"message": record.getMessage()}
        payload.setdefault("severity", record.levelname)
        payload.setdefault("logger", record.name)
        return json.dumps(payload, sort_keys=True, default=_json_default)


def _json_default(value: Any) -> Any:
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, Enum):
        return value.value
    return str(value)


def _normalize_attribute_value(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, (bool, int, float, str)):
        return value
    return json.dumps(value, sort_keys=True, default=_json_default)


def _normalize_attributes(
    attributes: Mapping[str, Any] | None,
) -> dict[str, Any]:
    normalized: dict[str, Any] = {}
    if attributes is None:
        return normalized

    for key, value in attributes.items():
        normalized_value = _normalize_attribute_value(value)
        if normalized_value is not None:
            normalized[key] = normalized_value
    return normalized


class Observability(Protocol):
    config: ObservabilityConfig

    def emit_lifecycle_event(self, event: SimulationLifecycleEvent) -> None: ...

    def emit_counter(
        self,
        name: str,
        value: int = 1,
        attributes: Mapping[str, str] | None = None,
    ) -> None: ...

    def emit_histogram(
        self,
        name: str,
        value: float,
        attributes: Mapping[str, str] | None = None,
    ) -> None: ...

    def record_artifact_manifest(
        self, manifest: TracerArtifactManifest
    ) -> None: ...

    def span(
        self, name: str, attributes: Mapping[str, Any] | None = None
    ) -> AbstractContextManager: ...

    def flush(self) -> None: ...


@dataclass
class NoOpObservability:
    config: ObservabilityConfig = field(
        default_factory=ObservabilityConfig.disabled
    )

    def emit_lifecycle_event(self, event: SimulationLifecycleEvent) -> None:
        return None

    def emit_counter(
        self,
        name: str,
        value: int = 1,
        attributes: Mapping[str, str] | None = None,
    ) -> None:
        return None

    def emit_histogram(
        self,
        name: str,
        value: float,
        attributes: Mapping[str, str] | None = None,
    ) -> None:
        return None

    def record_artifact_manifest(
        self, manifest: TracerArtifactManifest
    ) -> None:
        return None

    def span(
        self, name: str, attributes: Mapping[str, Any] | None = None
    ) -> NoOpSpan:
        return NoOpSpan()

    def flush(self) -> None:
        return None


@dataclass
class OtlpObservability:
    config: ObservabilityConfig
    tracer: Any
    meter: Any
    lifecycle_logger: logging.Logger
    tracer_provider: Any
    meter_provider: Any
    logger_provider: Any = None
    counter_cache: dict[str, Any] = field(default_factory=dict)
    histogram_cache: dict[str, Any] = field(default_factory=dict)

    def emit_lifecycle_event(self, event: SimulationLifecycleEvent) -> None:
        payload = event.model_dump(mode="json")
        self.lifecycle_logger.info(payload)

    def emit_counter(
        self,
        name: str,
        value: int = 1,
        attributes: Mapping[str, str] | None = None,
    ) -> None:
        counter = self.counter_cache.get(name)
        if counter is None:
            counter = self.meter.create_counter(name)
            self.counter_cache[name] = counter
        counter.add(value, attributes=_normalize_attributes(attributes))

    def emit_histogram(
        self,
        name: str,
        value: float,
        attributes: Mapping[str, str] | None = None,
    ) -> None:
        histogram = self.histogram_cache.get(name)
        if histogram is None:
            histogram = self.meter.create_histogram(name)
            self.histogram_cache[name] = histogram
        histogram.record(value, attributes=_normalize_attributes(attributes))

    def record_artifact_manifest(
        self, manifest: TracerArtifactManifest
    ) -> None:
        self.lifecycle_logger.info(
            {
                "event_name": "simulation.tracer.artifact_manifest",
                "manifest": manifest.model_dump(mode="json"),
            }
        )

    def span(
        self, name: str, attributes: Mapping[str, Any] | None = None
    ) -> OTelSpan:
        return OTelSpan(
            self.tracer.start_as_current_span(
                name,
                attributes=_normalize_attributes(attributes),
            )
        )

    def flush(self) -> None:
        if self.tracer_provider is not None:
            self.tracer_provider.force_flush()
        if self.meter_provider is not None:
            self.meter_provider.force_flush()
        if self.logger_provider is not None:
            self.logger_provider.force_flush()
