from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class InternalObservabilityModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class InternalObservabilityBackendHealth(InternalObservabilityModel):
    backend: str
    configured: bool
    reachable: bool | None = None
    checked_at: datetime
    detail: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class InternalObservabilityHealthResponse(InternalObservabilityModel):
    status: str
    backends: list[InternalObservabilityBackendHealth] = Field(
        default_factory=list
    )


class InternalObservabilityBackendCapability(InternalObservabilityModel):
    backend: str
    configured: bool
    operations: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class InternalObservabilityRouteDescriptor(InternalObservabilityModel):
    method: str
    path: str
    description: str


class InternalObservabilityCapabilitiesResponse(InternalObservabilityModel):
    auth_scheme: str
    backends: list[InternalObservabilityBackendCapability] = Field(
        default_factory=list
    )
    routes: list[InternalObservabilityRouteDescriptor] = Field(
        default_factory=list
    )
