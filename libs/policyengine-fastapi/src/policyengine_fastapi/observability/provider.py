from __future__ import annotations

import logging
import socket

from opentelemetry.sdk.resources import (
    DEPLOYMENT_ENVIRONMENT,
    SERVICE_INSTANCE_ID,
    SERVICE_NAME,
    SERVICE_NAMESPACE,
    Resource,
)

from .config import ObservabilityConfig
from .emitters import (
    JsonPayloadFormatter,
    NoOpObservability,
    Observability,
    OtlpObservability,
)

_CACHE: dict[tuple, Observability] = {}


def _cache_key(config: ObservabilityConfig) -> tuple:
    return (
        config.enabled,
        config.shadow_mode,
        config.service_name,
        config.environment,
        config.otlp_endpoint,
        tuple(sorted(config.otlp_headers.items())),
        config.artifact_bucket,
        config.artifact_prefix,
        config.tracer_capture_mode.value,
        config.slow_run_threshold_seconds,
    )


def _build_resource(config: ObservabilityConfig) -> Resource:
    return Resource.create(
        {
            SERVICE_NAME: config.service_name,
            SERVICE_NAMESPACE: "policyengine",
            DEPLOYMENT_ENVIRONMENT: config.environment,
            SERVICE_INSTANCE_ID: socket.gethostname(),
        }
    )


def _build_real_observability(config: ObservabilityConfig) -> Observability:
    from opentelemetry.exporter.otlp.proto.http.metric_exporter import (
        OTLPMetricExporter,
    )
    from opentelemetry.exporter.otlp.proto.http.trace_exporter import (
        OTLPSpanExporter,
    )
    from opentelemetry.sdk._logs import LoggerProvider, LoggingHandler
    from opentelemetry.sdk._logs.export import BatchLogRecordProcessor
    from opentelemetry.sdk.metrics import MeterProvider
    from opentelemetry.sdk.metrics.export import (
        PeriodicExportingMetricReader,
    )
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor

    resource = _build_resource(config)

    tracer_provider = TracerProvider(resource=resource)
    meter_provider = MeterProvider(resource=resource)
    logger_provider = None
    logging_handler = None

    if config.otlp_endpoint:
        headers = config.otlp_headers or None
        span_exporter = OTLPSpanExporter(
            endpoint=f"{config.otlp_endpoint.rstrip('/')}/v1/traces",
            headers=headers,
        )
        tracer_provider.add_span_processor(BatchSpanProcessor(span_exporter))

        metric_exporter = OTLPMetricExporter(
            endpoint=f"{config.otlp_endpoint.rstrip('/')}/v1/metrics",
            headers=headers,
        )
        meter_provider = MeterProvider(
            resource=resource,
            metric_readers=[PeriodicExportingMetricReader(metric_exporter)],
        )

        from opentelemetry.exporter.otlp.proto.http._log_exporter import (
            OTLPLogExporter,
        )

        logger_provider = LoggerProvider(resource=resource)
        logger_provider.add_log_record_processor(
            BatchLogRecordProcessor(
                OTLPLogExporter(
                    endpoint=f"{config.otlp_endpoint.rstrip('/')}/v1/logs",
                    headers=headers,
                )
            )
        )
        logging_handler = LoggingHandler(
            level=logging.INFO,
            logger_provider=logger_provider,
        )

    tracer = tracer_provider.get_tracer(config.service_name)
    meter = meter_provider.get_meter(config.service_name)

    lifecycle_logger = logging.getLogger(
        f"policyengine.observability.{config.service_name}"
    )
    lifecycle_logger.setLevel(logging.INFO)
    lifecycle_logger.propagate = False

    lifecycle_logger.handlers = []
    stream_handler = logging.StreamHandler()
    formatter = JsonPayloadFormatter()
    stream_handler.setFormatter(formatter)
    lifecycle_logger.addHandler(stream_handler)
    if logging_handler is not None:
        logging_handler.setFormatter(formatter)
        lifecycle_logger.addHandler(logging_handler)

    return OtlpObservability(
        config=config,
        tracer=tracer,
        meter=meter,
        lifecycle_logger=lifecycle_logger,
        tracer_provider=tracer_provider,
        meter_provider=meter_provider,
        logger_provider=logger_provider,
    )


def build_observability(
    config: ObservabilityConfig | None = None,
) -> Observability:
    if config is None:
        config = ObservabilityConfig.disabled()

    if not config.enabled:
        return NoOpObservability(config=config)

    key = _cache_key(config)
    cached = _CACHE.get(key)
    if cached is not None:
        return cached

    built = _build_real_observability(config)
    _CACHE[key] = built
    return built


def get_observability(
    config: ObservabilityConfig | None = None,
) -> Observability:
    return build_observability(config)


def reset_observability_cache() -> None:
    for value in _CACHE.values():
        value.flush()
        tracer_provider = getattr(value, "tracer_provider", None)
        if tracer_provider is not None:
            tracer_provider.shutdown()
        meter_provider = getattr(value, "meter_provider", None)
        if meter_provider is not None:
            meter_provider.shutdown()
        logger_provider = getattr(value, "logger_provider", None)
        if logger_provider is not None:
            logger_provider.shutdown()
    _CACHE.clear()
