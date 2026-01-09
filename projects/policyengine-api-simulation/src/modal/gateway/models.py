"""
Pydantic models for the Gateway API.
"""

from typing import Optional
from pydantic import BaseModel, ConfigDict


class SimulationRequest(BaseModel):
    """Request model for simulation submission."""

    country: str
    version: Optional[str] = None

    model_config = ConfigDict(extra="allow")  # Pass through all other fields


class JobSubmitResponse(BaseModel):
    """Response model for job submission."""

    job_id: str
    status: str
    poll_url: str
    country: str
    version: str


class JobStatusResponse(BaseModel):
    """Response model for job status polling."""

    status: str
    result: Optional[dict] = None
    error: Optional[str] = None
