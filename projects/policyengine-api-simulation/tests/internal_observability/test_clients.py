from __future__ import annotations

from types import SimpleNamespace

from policyengine_api_simulation.internal_observability.clients import (
    ArtifactStorageClient,
    HttpResponse,
    LokiClient,
    PrometheusClient,
    TempoClient,
    VersionCatalogClient,
    parse_gs_uri,
)


class RecordingTransport:
    def __init__(self, responses: list[HttpResponse]):
        self.responses = list(responses)
        self.calls = []

    def request(self, *, method, url, headers=None, params=None):
        self.calls.append(
            {
                "method": method,
                "url": url,
                "headers": dict(headers or {}),
                "params": dict(params or {}),
            }
        )
        return self.responses.pop(0)


def test_loki_client__uses_ready_and_query_range_routes():
    transport = RecordingTransport(
        [
            HttpResponse(status_code=200, body=None, text="ready"),
            HttpResponse(status_code=200, body={"data": {"result": []}}, text="{}"),
        ]
    )
    client = LokiClient(
        base_url="https://loki.example/",
        headers={"Authorization": "Bearer token"},
        transport=transport,
    )

    ready = client.ready()
    result = client.query_logs(query='{service="worker"}', limit=50)

    assert ready.reachable is True
    assert transport.calls[0]["url"] == "https://loki.example/ready"
    assert transport.calls[1]["url"] == "https://loki.example/loki/api/v1/query_range"
    assert transport.calls[1]["params"]["limit"] == 50
    assert result == {"data": {"result": []}}


def test_tempo_and_prometheus_clients__use_expected_endpoints():
    tempo_transport = RecordingTransport(
        [
            HttpResponse(status_code=200, body=None, text="ready"),
            HttpResponse(status_code=200, body={"trace": {}}, text="{}"),
            HttpResponse(status_code=200, body={"traces": []}, text="{}"),
        ]
    )
    tempo = TempoClient(base_url="https://tempo.example", transport=tempo_transport)

    prom_transport = RecordingTransport(
        [
            HttpResponse(status_code=200, body=None, text="ready"),
            HttpResponse(status_code=200, body={"data": {}}, text="{}"),
            HttpResponse(status_code=200, body={"data": {"result": []}}, text="{}"),
        ]
    )
    prometheus = PrometheusClient(
        base_url="https://prom.example/",
        transport=prom_transport,
    )

    assert tempo.ready().reachable is True
    assert tempo.get_trace("trace-123") == {"trace": {}}
    assert tempo.search_traces(tags={"run_id": "run-123"}, limit=5) == {
        "traces": []
    }
    assert tempo_transport.calls[1]["url"] == "https://tempo.example/api/traces/trace-123"
    assert tempo_transport.calls[2]["params"]["tags"] == "run_id=run-123"

    assert prometheus.ready().reachable is True
    assert prometheus.query(query="up") == {"data": {}}
    assert prometheus.query_range(
        query="histogram_quantile(...)",
        start="1",
        end="2",
        step="60s",
    ) == {"data": {"result": []}}
    assert prom_transport.calls[0]["url"] == "https://prom.example/-/ready"
    assert prom_transport.calls[2]["params"]["step"] == "60s"


def test_version_catalog_client_and_artifact_storage_client__expose_expected_contracts():
    service = SimpleNamespace(
        get_all_snapshots=lambda: {
            "us": SimpleNamespace(latest_version="1.632.5", versions=[1, 2]),
            "uk": SimpleNamespace(latest_version="2.78.0", versions=[1]),
        }
    )
    version_catalog = VersionCatalogClient(service)

    assert version_catalog.ready().metadata == {
        "us": {"latest_version": "1.632.5", "version_count": 2},
        "uk": {"latest_version": "2.78.0", "version_count": 1},
    }
    assert version_catalog.get_all_snapshots()["us"].latest_version == "1.632.5"

    class FakeBlob:
        def __init__(self, exists_result=True):
            self._exists_result = exists_result

        def exists(self):
            return self._exists_result

        def download_as_text(self):
            return '{"ok": true}'

    class FakeBucket:
        def blob(self, name):
            return FakeBlob()

    class FakeStorageClient:
        def lookup_bucket(self, name):
            return object()

        def bucket(self, name):
            return FakeBucket()

    artifact_client = ArtifactStorageClient(
        bucket_name="diagnostics",
        client=FakeStorageClient(),
    )

    assert artifact_client.ready().reachable is True
    assert artifact_client.exists("gs://diagnostics/runs/run-123.json") is True
    assert artifact_client.read_json("gs://diagnostics/runs/run-123.json") == {
        "ok": True
    }
    assert parse_gs_uri("gs://diagnostics/runs/run-123.json") == (
        "diagnostics",
        "runs/run-123.json",
    )
