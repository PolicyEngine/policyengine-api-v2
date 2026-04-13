from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends

from .contracts import (
    InternalObservabilityCapabilitiesResponse,
    InternalObservabilityHealthResponse,
)
from .query_service import InternalObservabilityQueryService
from .service import (
    get_internal_observability_query_service,
    require_internal_observability_access,
)


def create_router() -> APIRouter:
    router = APIRouter(
        prefix="/internal/observability",
        tags=["internal-observability"],
        dependencies=[Depends(require_internal_observability_access)],
    )

    @router.get("/health", response_model=InternalObservabilityHealthResponse)
    async def get_health(
        query_service: Annotated[
            InternalObservabilityQueryService,
            Depends(get_internal_observability_query_service),
        ],
    ) -> InternalObservabilityHealthResponse:
        return query_service.get_health()

    @router.get(
        "/capabilities",
        response_model=InternalObservabilityCapabilitiesResponse,
    )
    async def get_capabilities(
        query_service: Annotated[
            InternalObservabilityQueryService,
            Depends(get_internal_observability_query_service),
        ],
    ) -> InternalObservabilityCapabilitiesResponse:
        return query_service.get_capabilities()

    return router
