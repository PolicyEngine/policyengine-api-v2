from datetime import datetime, UTC

from opentelemetry.sdk._logs.export import LogExportResult
from opentelemetry.sdk.metrics.export import MetricExportResult
from opentelemetry.sdk.trace.export import SpanExportResult
from policyengine_fastapi.observability import (
    NoOpObservability,
    ObservabilityConfig,
    OtlpObservability,
    SimulationCompositeTraceResponse,
    SimulationLifecycleEvent,
    SimulationRunSummary,
    SimulationStage,
    SimulationTelemetryEnvelope,
    SimulationTimelineEntry,
    TracerArtifactManifest,
    TracerCaptureMode,
    VersionStageMetricResponse,
    build_observability,
    generate_run_id,
    get_observability,
    parse_bool,
    parse_header_value_pairs,
    reset_observability_cache,
    stable_config_hash,
)
from pydantic import ValidationError


def test_parse_header_value_pairs__supports_commas_and_newlines():
    raw = "Authorization=Bearer abc,\nX-Scope=production"

    assert parse_header_value_pairs(raw) == {
        "Authorization": "Bearer abc",
        "X-Scope": "production",
    }


def test_parse_header_value_pairs__raises_for_invalid_pair():
    try:
        parse_header_value_pairs("Authorization")
    except ValueError as error:
        assert "key=value" in str(error)
    else:
        raise AssertionError("Expected invalid OTLP header parsing to fail")


def test_parse_bool__supports_common_truthy_and_falsey_values():
    assert parse_bool("true") is True
    assert parse_bool("YES") is True
    assert parse_bool("0") is False
    assert parse_bool(None, default=True) is True


def test_observability_config_disabled__returns_disabled_defaults():
    config = ObservabilityConfig.disabled(service_name="test-service")

    assert config.enabled is False
    assert config.service_name == "test-service"
    assert config.otlp_headers == {}
    assert config.tracer_capture_mode == TracerCaptureMode.DISABLED


def test_correlation_helpers__generate_ids_and_stable_hashes():
    run_id = generate_run_id()
    left = stable_config_hash({"b": 2, "a": 1})
    right = stable_config_hash({"a": 1, "b": 2})

    assert len(run_id) == 36
    assert left == right
    assert left.startswith("sha256:")


def test_contract_models__serialize_expected_shapes():
    timestamp = datetime(2026, 4, 9, 20, 0, tzinfo=UTC)

    event = SimulationLifecycleEvent(
        event_name="simulation.stage.completed",
        stage=SimulationStage.WORKER_SIMULATION_CONSTRUCTED,
        status="ok",
        timestamp=timestamp,
        service="policyengine-simulation-worker",
        run_id="run-123",
    )
    manifest = TracerArtifactManifest(
        run_id="run-123",
        scenario="baseline",
        capture_mode=TracerCaptureMode.THRESHOLD,
        artifact_format="policyengine.flat_trace.v1",
        storage_uri="gs://bucket/run-123/trace.json.gz",
        generated_at=timestamp,
    )
    response = SimulationCompositeTraceResponse(
        run=SimulationRunSummary(run_id="run-123", status="complete"),
        timeline=[
            SimulationTimelineEntry(
                stage=SimulationStage.REQUEST_ACCEPTED,
                started_at=timestamp,
                ended_at=timestamp,
                duration_seconds=0.0,
                service="policyengine-api",
            )
        ],
        tracer={"baseline": {"manifest": manifest.model_dump(mode="json")}},
    )
    version_metrics = VersionStageMetricResponse(
        country="us",
        window={"from": timestamp, "to": timestamp},
    )

    dumped_event = event.model_dump(mode="json")
    dumped_response = response.model_dump(mode="json")
    dumped_version_metrics = version_metrics.model_dump(mode="json")

    assert dumped_event["stage"] == "worker.simulation.constructed"
    assert dumped_response["timeline"][0]["stage"] == "request.accepted"
    assert (
        dumped_response["tracer"]["baseline"]["manifest"]["capture_mode"]
        == "threshold"
    )
    assert dumped_version_metrics["versions"] == []


def test_telemetry_envelope__serializes_expected_defaults():
    envelope = SimulationTelemetryEnvelope(run_id="run-123")

    dumped = envelope.model_dump(mode="json")

    assert dumped["run_id"] == "run-123"
    assert dumped["capture_mode"] == "disabled"


def test_contract_models__reject_extra_fields():
    try:
        SimulationLifecycleEvent(
            event_name="simulation.stage.completed",
            stage=SimulationStage.WORKER_COMPLETED,
            status="ok",
            timestamp=datetime(2026, 4, 9, 20, 0, tzinfo=UTC),
            service="policyengine-simulation-worker",
            run_id="run-789",
            unexpected=True,
        )
    except ValidationError as error:
        assert "unexpected" in str(error)
    else:
        raise AssertionError("Expected extra field validation to fail")


def test_contract_models__reject_invalid_enum_values():
    try:
        SimulationTelemetryEnvelope(run_id="run-123", capture_mode="bad-mode")
    except ValidationError as error:
        assert "capture_mode" in str(error)
    else:
        raise AssertionError("Expected invalid enum validation to fail")


def test_noop_observability__accepts_calls_without_side_effects():
    observability = NoOpObservability()
    event = SimulationLifecycleEvent(
        event_name="simulation.stage.completed",
        stage=SimulationStage.WORKER_COMPLETED,
        status="ok",
        timestamp=datetime(2026, 4, 9, 20, 0, tzinfo=UTC),
        service="policyengine-simulation-worker",
        run_id="run-456",
    )

    observability.emit_lifecycle_event(event)
    observability.emit_counter("policyengine.simulation.run.count")
    observability.emit_histogram(
        "policyengine.simulation.run.duration.seconds", 1.23
    )
    with observability.span("run_simulation") as span:
        span.set_attribute("run_id", "run-456")
        span.add_event("simulation.completed")
    observability.flush()


def test_observability_provider__returns_noop_for_disabled_defaults():
    observability = build_observability()

    assert isinstance(observability, NoOpObservability)
    assert observability.config == ObservabilityConfig.disabled()


def test_observability_provider__preserves_supplied_config(monkeypatch):
    reset_observability_cache()
    monkeypatch.setattr(
        "opentelemetry.exporter.otlp.proto.http.trace_exporter.OTLPSpanExporter.export",
        lambda self, spans: SpanExportResult.SUCCESS,
    )
    monkeypatch.setattr(
        "opentelemetry.exporter.otlp.proto.http.metric_exporter.OTLPMetricExporter.export",
        lambda self, metrics_data, timeout_millis=10000: MetricExportResult.SUCCESS,
    )
    monkeypatch.setattr(
        "opentelemetry.exporter.otlp.proto.http._log_exporter.OTLPLogExporter.export",
        lambda self, batch: LogExportResult.SUCCESS,
    )
    config = ObservabilityConfig(
        enabled=True,
        service_name="simulation-worker",
        otlp_endpoint="https://otlp.example",
        tracer_capture_mode=TracerCaptureMode.THRESHOLD,
    )

    built = build_observability(config)
    fetched = get_observability(config)

    assert isinstance(built, OtlpObservability)
    assert built.config == config
    assert isinstance(fetched, OtlpObservability)
    assert fetched is built
    built.emit_lifecycle_event(
        SimulationLifecycleEvent(
            event_name="simulation.stage.completed",
            stage=SimulationStage.WORKER_COMPLETED,
            status="ok",
            timestamp=datetime(2026, 4, 9, 20, 0, tzinfo=UTC),
            service="policyengine-simulation-worker",
            run_id="run-456",
        )
    )
    built.emit_counter(
        "policyengine.simulation.run.count",
        attributes={"status": "submitted"},
    )
    built.emit_histogram(
        "policyengine.simulation.run.duration.seconds",
        1.23,
        attributes={"status": "complete"},
    )
    with built.span("run_simulation", attributes={"run_id": "run-456"}) as span:
        span.add_event("simulation.completed")
    built.flush()
    reset_observability_cache()
