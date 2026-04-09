"""
Pydantic models for the Gateway API.
"""

from typing import Optional
from pydantic import BaseModel, ConfigDict, model_validator

from src.modal.telemetry import TelemetryEnvelope


class SimulationRequest(BaseModel):
    """Request model for simulation submission."""

    country: str
    version: Optional[str] = None
    telemetry: TelemetryEnvelope | None = None

    model_config = ConfigDict(
        extra="allow",
        populate_by_name=True,
    )  # Pass through all other fields

    @model_validator(mode="before")
    @classmethod
    def move_internal_telemetry_alias(cls, value):
        if not isinstance(value, dict):
            return value
        if "telemetry" in value or "_telemetry" not in value:
            return value

        normalized = dict(value)
        normalized["telemetry"] = normalized.pop("_telemetry")
        return normalized


class JobSubmitResponse(BaseModel):
    """Response model for job submission."""

    job_id: str
    status: str
    poll_url: str
    country: str
    version: str
    run_id: Optional[str] = None


class JobStatusResponse(BaseModel):
    """Response model for job status polling."""

    status: str
    run_id: Optional[str] = None
    result: Optional[dict] = None
    error: Optional[str] = None


class PingRequest(BaseModel):
    """Request model for ping endpoint."""

    value: int


class PingResponse(BaseModel):
    """Response model for ping endpoint."""

    incremented: int
