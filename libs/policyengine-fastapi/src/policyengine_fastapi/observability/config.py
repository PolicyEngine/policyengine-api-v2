from __future__ import annotations

from dataclasses import dataclass, field
import os

from .stages import TracerCaptureMode


def parse_header_value_pairs(raw: str | None) -> dict[str, str]:
    """Parse OTLP headers from a comma or newline separated key=value string."""

    if raw is None:
        return {}

    stripped = raw.strip()
    if not stripped:
        return {}

    headers: dict[str, str] = {}
    for pair in stripped.replace("\n", ",").split(","):
        candidate = pair.strip()
        if not candidate:
            continue
        key, separator, value = candidate.partition("=")
        if not separator:
            raise ValueError(
                "Expected OTLP headers in key=value format separated by commas"
            )
        headers[key.strip()] = value.strip()

    return headers


def parse_bool(raw: str | bool | None, default: bool = False) -> bool:
    if raw is None:
        return default
    if isinstance(raw, bool):
        return raw
    return raw.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class ObservabilityConfig:
    enabled: bool = False
    shadow_mode: bool = True
    service_name: str = "policyengine-observability"
    environment: str = "production"
    otlp_endpoint: str | None = None
    otlp_headers: dict[str, str] = field(default_factory=dict)
    artifact_bucket: str | None = None
    artifact_prefix: str = "simulation-observability"
    tracer_capture_mode: TracerCaptureMode = TracerCaptureMode.DISABLED
    slow_run_threshold_seconds: float = 30.0

    @classmethod
    def disabled(cls, service_name: str = "policyengine-observability"):
        return cls(enabled=False, service_name=service_name)

    @classmethod
    def from_env(
        cls,
        service_name: str,
        environment: str = "production",
        prefix: str = "OBSERVABILITY_",
    ) -> "ObservabilityConfig":
        return cls(
            enabled=parse_bool(os.getenv(f"{prefix}ENABLED"), default=False),
            shadow_mode=parse_bool(
                os.getenv(f"{prefix}SHADOW_MODE"),
                default=True,
            ),
            service_name=os.getenv(f"{prefix}SERVICE_NAME", service_name),
            environment=os.getenv(f"{prefix}ENVIRONMENT", environment),
            otlp_endpoint=os.getenv(f"{prefix}OTLP_ENDPOINT"),
            otlp_headers=parse_header_value_pairs(os.getenv(f"{prefix}OTLP_HEADERS")),
            artifact_bucket=os.getenv(f"{prefix}ARTIFACT_BUCKET"),
            artifact_prefix=os.getenv(
                f"{prefix}ARTIFACT_PREFIX",
                "simulation-observability",
            ),
            tracer_capture_mode=TracerCaptureMode(
                os.getenv(
                    f"{prefix}TRACER_CAPTURE_MODE",
                    TracerCaptureMode.DISABLED.value,
                )
            ),
            slow_run_threshold_seconds=float(
                os.getenv(f"{prefix}SLOW_RUN_THRESHOLD_SECONDS", "30.0")
            ),
        )
