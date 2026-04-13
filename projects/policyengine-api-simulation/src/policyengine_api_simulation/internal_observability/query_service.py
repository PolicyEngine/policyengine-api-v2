from __future__ import annotations

from dataclasses import dataclass

from .clients import (
    ArtifactStorageClient,
    LokiClient,
    PrometheusClient,
    TempoClient,
    VersionCatalogClient,
)
from .contracts import (
    InternalObservabilityBackendCapability,
    InternalObservabilityBackendHealth,
    InternalObservabilityCapabilitiesResponse,
    InternalObservabilityHealthResponse,
    InternalObservabilityRouteDescriptor,
)


@dataclass(frozen=True)
class InternalObservabilityQueryService:
    loki: LokiClient
    tempo: TempoClient
    prometheus: PrometheusClient
    version_catalog: VersionCatalogClient
    artifact_storage: ArtifactStorageClient

    def get_capabilities(self) -> InternalObservabilityCapabilitiesResponse:
        return InternalObservabilityCapabilitiesResponse(
            auth_scheme="bearer_token",
            backends=[
                InternalObservabilityBackendCapability(
                    backend="loki",
                    configured=self.loki.configured,
                    operations=["ready", "query_logs"],
                ),
                InternalObservabilityBackendCapability(
                    backend="tempo",
                    configured=self.tempo.configured,
                    operations=["ready", "get_trace", "search_traces"],
                ),
                InternalObservabilityBackendCapability(
                    backend="prometheus",
                    configured=self.prometheus.configured,
                    operations=["ready", "query", "query_range"],
                ),
                InternalObservabilityBackendCapability(
                    backend="version_catalog",
                    configured=self.version_catalog.configured,
                    operations=["ready", "get_all_snapshots"],
                ),
                InternalObservabilityBackendCapability(
                    backend="artifact_storage",
                    configured=self.artifact_storage.configured,
                    operations=["ready", "exists", "read_json", "read_text"],
                ),
            ],
            routes=[
                InternalObservabilityRouteDescriptor(
                    method="GET",
                    path="/internal/observability/health",
                    description="Internal backend connectivity and configuration status.",
                ),
                InternalObservabilityRouteDescriptor(
                    method="GET",
                    path="/internal/observability/capabilities",
                    description="Available backend clients and supported internal operations.",
                ),
            ],
        )

    def get_health(self) -> InternalObservabilityHealthResponse:
        backends = [
            self._to_health_model("loki", self.loki.ready()),
            self._to_health_model("tempo", self.tempo.ready()),
            self._to_health_model("prometheus", self.prometheus.ready()),
            self._to_health_model(
                "version_catalog",
                self.version_catalog.ready(),
            ),
            self._to_health_model(
                "artifact_storage",
                self.artifact_storage.ready(),
            ),
        ]

        configured = [backend for backend in backends if backend.configured]
        reachable = [backend for backend in configured if backend.reachable]
        if not configured:
            status = "unavailable"
        elif len(reachable) == len(configured):
            status = "ok"
        else:
            status = "degraded"

        return InternalObservabilityHealthResponse(
            status=status,
            backends=backends,
        )

    @staticmethod
    def _to_health_model(
        backend: str,
        status,
    ) -> InternalObservabilityBackendHealth:
        from datetime import UTC, datetime

        return InternalObservabilityBackendHealth(
            backend=backend,
            configured=status.configured,
            reachable=status.reachable,
            checked_at=datetime.now(UTC),
            detail=status.detail,
            metadata=dict(status.metadata or {}),
        )
