from __future__ import annotations

from functools import lru_cache

import modal
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from policyengine_fastapi.observability import parse_header_value_pairs

from policyengine_api_simulation.settings import AppSettings, get_settings
from policyengine_api_simulation.version_catalog import VersionCatalogService

from .clients import (
    ArtifactStorageClient,
    LokiClient,
    PrometheusClient,
    TempoClient,
    VersionCatalogClient,
)
from .query_service import InternalObservabilityQueryService

bearer_scheme = HTTPBearer(auto_error=False)


def require_internal_observability_access(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    settings: AppSettings = Depends(get_settings),
) -> None:
    token = settings.observability_internal_api_token
    if not token:
        raise HTTPException(
            status_code=503,
            detail="Internal observability API token is not configured",
        )
    if credentials is None or credentials.credentials != token:
        raise HTTPException(status_code=401, detail="Invalid internal API token")


@lru_cache
def build_internal_observability_query_service() -> InternalObservabilityQueryService:
    settings = get_settings()
    version_catalog_service = VersionCatalogService(
        loader=lambda dict_name, environment: modal.Dict.from_name(
            dict_name,
            environment_name=environment,
        ),
        environment=settings.observability_version_catalog_environment,
    )
    return InternalObservabilityQueryService(
        loki=LokiClient(
            base_url=settings.observability_loki_base_url,
            headers=parse_header_value_pairs(settings.observability_loki_headers),
        ),
        tempo=TempoClient(
            base_url=settings.observability_tempo_base_url,
            headers=parse_header_value_pairs(settings.observability_tempo_headers),
        ),
        prometheus=PrometheusClient(
            base_url=settings.observability_prometheus_base_url,
            headers=parse_header_value_pairs(
                settings.observability_prometheus_headers
            ),
        ),
        version_catalog=VersionCatalogClient(version_catalog_service),
        artifact_storage=ArtifactStorageClient(
            bucket_name=settings.observability_artifact_bucket,
        ),
    )


def get_internal_observability_query_service() -> InternalObservabilityQueryService:
    return build_internal_observability_query_service()


def reset_internal_observability_query_service_cache() -> None:
    build_internal_observability_query_service.cache_clear()
