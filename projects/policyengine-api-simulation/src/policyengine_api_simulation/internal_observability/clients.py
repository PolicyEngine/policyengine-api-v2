from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
import json
from typing import Any, Mapping, Protocol
from urllib import error, parse, request

from google.cloud import storage

from policyengine_api_simulation.version_catalog import VersionCatalogService


JsonValue = dict[str, Any] | list[Any] | str | int | float | bool | None


@dataclass(frozen=True)
class HttpResponse:
    status_code: int
    body: JsonValue | None
    text: str


class HttpTransport(Protocol):
    def request(
        self,
        *,
        method: str,
        url: str,
        headers: Mapping[str, str] | None = None,
        params: Mapping[str, Any] | None = None,
    ) -> HttpResponse: ...


class UrllibHttpTransport:
    def request(
        self,
        *,
        method: str,
        url: str,
        headers: Mapping[str, str] | None = None,
        params: Mapping[str, Any] | None = None,
    ) -> HttpResponse:
        final_url = _append_query_params(url, params)
        req = request.Request(
            final_url,
            method=method.upper(),
            headers=dict(headers or {}),
        )
        try:
            with request.urlopen(req) as response:
                text = response.read().decode("utf-8")
                return HttpResponse(
                    status_code=response.status,
                    body=_parse_json_body(text),
                    text=text,
                )
        except error.HTTPError as exc:
            text = exc.read().decode("utf-8")
            return HttpResponse(
                status_code=exc.code,
                body=_parse_json_body(text),
                text=text,
            )


def _append_query_params(
    url: str,
    params: Mapping[str, Any] | None = None,
) -> str:
    if not params:
        return url

    normalized = {
        key: value
        for key, value in params.items()
        if value is not None
    }
    if not normalized:
        return url

    encoded = parse.urlencode(normalized, doseq=True)
    separator = "&" if "?" in url else "?"
    return f"{url}{separator}{encoded}"


def _parse_json_body(text: str) -> JsonValue | None:
    if not text:
        return None
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return None


@dataclass(frozen=True)
class BackendStatus:
    configured: bool
    reachable: bool | None
    detail: str | None = None
    metadata: dict[str, Any] | None = None


class LokiClient:
    def __init__(
        self,
        *,
        base_url: str | None,
        headers: Mapping[str, str] | None = None,
        transport: HttpTransport | None = None,
    ):
        self.base_url = _normalize_base_url(base_url)
        self.headers = dict(headers or {})
        self.transport = transport or UrllibHttpTransport()

    @property
    def configured(self) -> bool:
        return self.base_url is not None

    def ready(self) -> BackendStatus:
        if not self.configured:
            return BackendStatus(False, None, "Loki base URL is not configured")
        response = self.transport.request(
            method="GET",
            url=f"{self.base_url}/ready",
            headers=self.headers,
        )
        return BackendStatus(
            True,
            response.status_code == 200,
            f"HTTP {response.status_code}",
        )

    def query_logs(
        self,
        *,
        query: str,
        start: str | None = None,
        end: str | None = None,
        limit: int = 100,
    ) -> JsonValue | None:
        if not self.configured:
            raise ValueError("Loki client is not configured")
        response = self.transport.request(
            method="GET",
            url=f"{self.base_url}/loki/api/v1/query_range",
            headers=self.headers,
            params={
                "query": query,
                "start": start,
                "end": end,
                "limit": limit,
            },
        )
        return response.body


class TempoClient:
    def __init__(
        self,
        *,
        base_url: str | None,
        headers: Mapping[str, str] | None = None,
        transport: HttpTransport | None = None,
    ):
        self.base_url = _normalize_base_url(base_url)
        self.headers = dict(headers or {})
        self.transport = transport or UrllibHttpTransport()

    @property
    def configured(self) -> bool:
        return self.base_url is not None

    def ready(self) -> BackendStatus:
        if not self.configured:
            return BackendStatus(False, None, "Tempo base URL is not configured")
        response = self.transport.request(
            method="GET",
            url=f"{self.base_url}/ready",
            headers=self.headers,
        )
        return BackendStatus(
            True,
            response.status_code == 200,
            f"HTTP {response.status_code}",
        )

    def get_trace(self, trace_id: str) -> JsonValue | None:
        if not self.configured:
            raise ValueError("Tempo client is not configured")
        response = self.transport.request(
            method="GET",
            url=f"{self.base_url}/api/traces/{trace_id}",
            headers=self.headers,
        )
        return response.body

    def search_traces(
        self,
        *,
        tags: Mapping[str, Any] | None = None,
        start: str | None = None,
        end: str | None = None,
        limit: int = 20,
    ) -> JsonValue | None:
        if not self.configured:
            raise ValueError("Tempo client is not configured")
        params = {"start": start, "end": end, "limit": limit}
        if tags:
            params["tags"] = ",".join(f"{k}={v}" for k, v in tags.items())
        response = self.transport.request(
            method="GET",
            url=f"{self.base_url}/api/search",
            headers=self.headers,
            params=params,
        )
        return response.body


class PrometheusClient:
    def __init__(
        self,
        *,
        base_url: str | None,
        headers: Mapping[str, str] | None = None,
        transport: HttpTransport | None = None,
    ):
        self.base_url = _normalize_base_url(base_url)
        self.headers = dict(headers or {})
        self.transport = transport or UrllibHttpTransport()

    @property
    def configured(self) -> bool:
        return self.base_url is not None

    def ready(self) -> BackendStatus:
        if not self.configured:
            return BackendStatus(
                False,
                None,
                "Prometheus base URL is not configured",
            )
        response = self.transport.request(
            method="GET",
            url=f"{self.base_url}/-/ready",
            headers=self.headers,
        )
        return BackendStatus(
            True,
            response.status_code == 200,
            f"HTTP {response.status_code}",
        )

    def query(self, *, query: str, time: str | None = None) -> JsonValue | None:
        if not self.configured:
            raise ValueError("Prometheus client is not configured")
        response = self.transport.request(
            method="GET",
            url=f"{self.base_url}/api/v1/query",
            headers=self.headers,
            params={"query": query, "time": time},
        )
        return response.body

    def query_range(
        self,
        *,
        query: str,
        start: str,
        end: str,
        step: str,
    ) -> JsonValue | None:
        if not self.configured:
            raise ValueError("Prometheus client is not configured")
        response = self.transport.request(
            method="GET",
            url=f"{self.base_url}/api/v1/query_range",
            headers=self.headers,
            params={
                "query": query,
                "start": start,
                "end": end,
                "step": step,
            },
        )
        return response.body


class VersionCatalogClient:
    def __init__(self, service: VersionCatalogService):
        self.service = service

    @property
    def configured(self) -> bool:
        return True

    def ready(self) -> BackendStatus:
        try:
            snapshots = self.service.get_all_snapshots()
        except Exception as error:
            return BackendStatus(
                True,
                False,
                str(error),
            )
        metadata = {
            country: {
                "latest_version": snapshot.latest_version,
                "version_count": len(snapshot.versions),
            }
            for country, snapshot in snapshots.items()
        }
        return BackendStatus(
            True,
            True,
            "Loaded version catalog snapshots",
            metadata=metadata,
        )

    def get_all_snapshots(self):
        return self.service.get_all_snapshots()


class ArtifactStorageClient:
    def __init__(
        self,
        *,
        bucket_name: str | None,
        client: storage.Client | None = None,
    ):
        self.bucket_name = bucket_name
        self._client = client

    @property
    def configured(self) -> bool:
        return bool(self.bucket_name)

    def ready(self) -> BackendStatus:
        if not self.configured:
            return BackendStatus(
                False,
                None,
                "Artifact bucket is not configured",
            )
        bucket = self._get_client().lookup_bucket(self.bucket_name)
        return BackendStatus(
            True,
            bucket is not None,
            "Bucket reachable" if bucket is not None else "Bucket not found",
        )

    def exists(self, storage_uri: str) -> bool:
        bucket_name, blob_name = parse_gs_uri(storage_uri)
        return self._get_client().bucket(bucket_name).blob(blob_name).exists()

    def read_json(self, storage_uri: str) -> JsonValue:
        text = self.read_text(storage_uri)
        return json.loads(text)

    def read_text(self, storage_uri: str) -> str:
        bucket_name, blob_name = parse_gs_uri(storage_uri)
        return (
            self._get_client()
            .bucket(bucket_name)
            .blob(blob_name)
            .download_as_text()
        )

    def _get_client(self) -> storage.Client:
        if self._client is None:
            self._client = storage.Client()
        return self._client


def parse_gs_uri(storage_uri: str) -> tuple[str, str]:
    if not storage_uri.startswith("gs://"):
        raise ValueError(f"Expected gs:// URI, got: {storage_uri}")
    remainder = storage_uri[len("gs://") :]
    bucket_name, separator, blob_name = remainder.partition("/")
    if not separator or not bucket_name or not blob_name:
        raise ValueError(f"Invalid gs:// URI: {storage_uri}")
    return bucket_name, blob_name


def build_checked_backend_health(
    backend: str,
    status: BackendStatus,
) -> tuple[str, bool, bool | None, str | None, dict[str, Any], datetime]:
    return (
        backend,
        status.configured,
        status.reachable,
        status.detail,
        dict(status.metadata or {}),
        datetime.now(UTC),
    )


def _normalize_base_url(base_url: str | None) -> str | None:
    if base_url is None:
        return None
    stripped = base_url.strip().rstrip("/")
    return stripped or None
