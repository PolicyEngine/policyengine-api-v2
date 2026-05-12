"""Shared HTTP responses for gateway endpoints."""

from __future__ import annotations

from typing import Any

from fastapi.responses import JSONResponse

from src.modal.gateway.models import (
    BudgetWindowBatchStatusResponse,
    JobStatusResponse,
)


class AcceptedResponse(JSONResponse):
    """Shared 202 JSON response."""

    def __init__(self, content: dict):
        super().__init__(status_code=202, content=content)


class ServerErrorResponse(JSONResponse):
    """Shared 500 JSON response."""

    def __init__(self, content: dict):
        super().__init__(status_code=500, content=content)


def _omit_top_level_none(payload: dict) -> dict:
    return {key: value for key, value in payload.items() if value is not None}


def batch_status_payload(response: BudgetWindowBatchStatusResponse) -> dict:
    payload = response.model_dump(mode="json")
    if response.policyengine_bundle is not None:
        payload["policyengine_bundle"] = response.policyengine_bundle.model_dump(
            mode="json",
            exclude_none=True,
        )
    return payload


def batch_status_response(response: BudgetWindowBatchStatusResponse):
    payload = batch_status_payload(response)
    if response.status in {"submitted", "running"}:
        return AcceptedResponse(payload)
    if response.status == "failed":
        return ServerErrorResponse(payload)
    # Preserve null-valued annual sections inside outputsByYear. Returning the
    # model directly would let FastAPI's route-level exclude_none prune them.
    return JSONResponse(_omit_top_level_none(payload))


def complete_job_response(*, result: Any, job_metadata: dict | None = None):
    response = JobStatusResponse(
        status="complete",
        result=result,
        **(job_metadata or {}),
    )
    payload = response.model_dump(mode="json")
    if response.policyengine_bundle is not None:
        payload["policyengine_bundle"] = response.policyengine_bundle.model_dump(
            mode="json",
            exclude_none=True,
        )
    # Preserve null-valued legacy sections inside pass-through result payloads.
    return JSONResponse(_omit_top_level_none(payload))


def running_job_response(job_metadata: dict | None = None) -> AcceptedResponse:
    return AcceptedResponse(
        {
            "status": "running",
            "result": None,
            "error": None,
            **(job_metadata or {}),
        }
    )


def failed_job_response(
    *, error: str, job_metadata: dict | None = None
) -> ServerErrorResponse:
    return ServerErrorResponse(
        {
            "status": "failed",
            "result": None,
            "error": error,
            **(job_metadata or {}),
        }
    )
