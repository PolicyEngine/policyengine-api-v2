from policyengine_fastapi.observability import TracerCaptureMode
from policyengine_api_simulation.settings import get_settings


def test_settings_default_observability_config_is_disabled():
    get_settings.cache_clear()
    try:
        settings = get_settings()
    finally:
        get_settings.cache_clear()

    config = settings.observability

    assert config.enabled is False
    assert config.shadow_mode is True
    assert config.service_name == "policyengine-api-simulation"
    assert config.environment == settings.environment.value
    assert config.otlp_headers == {}
    assert config.tracer_capture_mode == TracerCaptureMode.DISABLED
    assert config.slow_run_threshold_seconds == 30.0
    assert config.tracer_success_sample_rate == 0.0
    assert config.tracer_include_computation_log is False
    assert settings.observability_internal_api_token is None
    assert settings.observability_loki_base_url is None
    assert settings.observability_tempo_base_url is None
    assert settings.observability_prometheus_base_url is None


def test_settings_expose_observability_config(monkeypatch):
    monkeypatch.setenv("OBSERVABILITY_ENABLED", "true")
    monkeypatch.setenv("OBSERVABILITY_SHADOW_MODE", "false")
    monkeypatch.setenv("OBSERVABILITY_SERVICE_NAME", "simulation-worker")
    monkeypatch.setenv("OBSERVABILITY_ENVIRONMENT", "staging")
    monkeypatch.setenv("OBSERVABILITY_OTLP_ENDPOINT", "https://otlp.example")
    monkeypatch.setenv(
        "OBSERVABILITY_OTLP_HEADERS",
        "Authorization=Bearer abc,X-Scope=ops",
    )
    monkeypatch.setenv("OBSERVABILITY_ARTIFACT_BUCKET", "test-bucket")
    monkeypatch.setenv("OBSERVABILITY_ARTIFACT_PREFIX", "diagnostics")
    monkeypatch.setenv("OBSERVABILITY_TRACER_CAPTURE_MODE", "threshold")
    monkeypatch.setenv("OBSERVABILITY_SLOW_RUN_THRESHOLD_SECONDS", "45.5")
    monkeypatch.setenv("OBSERVABILITY_TRACER_SUCCESS_SAMPLE_RATE", "0.15")
    monkeypatch.setenv("OBSERVABILITY_TRACER_INCLUDE_COMPUTATION_LOG", "true")
    monkeypatch.setenv("OBSERVABILITY_INTERNAL_API_TOKEN", "internal-token")
    monkeypatch.setenv("OBSERVABILITY_LOKI_BASE_URL", "https://loki.example")
    monkeypatch.setenv(
        "OBSERVABILITY_LOKI_HEADERS",
        "Authorization=Bearer loki-token",
    )
    monkeypatch.setenv("OBSERVABILITY_TEMPO_BASE_URL", "https://tempo.example")
    monkeypatch.setenv(
        "OBSERVABILITY_TEMPO_HEADERS",
        "Authorization=Bearer tempo-token",
    )
    monkeypatch.setenv(
        "OBSERVABILITY_PROMETHEUS_BASE_URL",
        "https://prom.example",
    )
    monkeypatch.setenv(
        "OBSERVABILITY_PROMETHEUS_HEADERS",
        "Authorization=Bearer prom-token",
    )
    monkeypatch.setenv(
        "OBSERVABILITY_VERSION_CATALOG_ENVIRONMENT",
        "staging",
    )

    get_settings.cache_clear()
    try:
        settings = get_settings()
    finally:
        get_settings.cache_clear()

    config = settings.observability

    assert config.enabled is True
    assert config.shadow_mode is False
    assert config.service_name == "simulation-worker"
    assert config.environment == "staging"
    assert config.otlp_endpoint == "https://otlp.example"
    assert config.otlp_headers == {
        "Authorization": "Bearer abc",
        "X-Scope": "ops",
    }
    assert config.artifact_bucket == "test-bucket"
    assert config.artifact_prefix == "diagnostics"
    assert config.tracer_capture_mode == TracerCaptureMode.THRESHOLD
    assert config.slow_run_threshold_seconds == 45.5
    assert config.tracer_success_sample_rate == 0.15
    assert config.tracer_include_computation_log is True
    assert settings.observability_internal_api_token == "internal-token"
    assert settings.observability_loki_base_url == "https://loki.example"
    assert settings.observability_loki_headers == "Authorization=Bearer loki-token"
    assert settings.observability_tempo_base_url == "https://tempo.example"
    assert settings.observability_tempo_headers == "Authorization=Bearer tempo-token"
    assert settings.observability_prometheus_base_url == "https://prom.example"
    assert (
        settings.observability_prometheus_headers
        == "Authorization=Bearer prom-token"
    )
    assert settings.observability_version_catalog_environment == "staging"
