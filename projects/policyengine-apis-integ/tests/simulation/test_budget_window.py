"""Integration tests for budget-window batch execution."""

from __future__ import annotations

import time
from http import HTTPStatus

import httpx
import pytest

from .conftest import settings


def _httpx_headers() -> dict[str, str]:
    if settings.access_token:
        return {"Authorization": f"Bearer {settings.access_token}"}
    return {}


def poll_for_budget_window_completion(
    batch_job_id: str,
    max_wait_seconds: float,
    poll_interval: float,
) -> dict:
    """Poll a budget-window batch until it reaches a terminal state."""

    start_time = time.time()
    timeout = settings.timeout_in_millis / 1000

    with httpx.Client(
        base_url=settings.base_url,
        headers=_httpx_headers(),
        timeout=timeout,
    ) as client:
        while time.time() - start_time < max_wait_seconds:
            response = client.get(f"/budget-window-jobs/{batch_job_id}")

            if response.status_code == HTTPStatus.OK:
                body = response.json()
                assert body["status"] == "complete", f"Unexpected payload: {body}"
                return body

            if response.status_code == HTTPStatus.INTERNAL_SERVER_ERROR:
                raise AssertionError(f"Budget-window batch failed: {response.text}")

            if response.status_code == HTTPStatus.ACCEPTED:
                time.sleep(poll_interval)
                continue

            raise AssertionError(
                f"Unexpected status code while polling budget-window batch: "
                f"{response.status_code} {response.text}"
            )

    raise TimeoutError(
        f"Budget-window batch {batch_job_id} did not complete within "
        f"{max_wait_seconds}s"
    )


@pytest.mark.beta_only
def test_budget_window_batch_completes_against_staging(
    us_model_version: str,
    max_wait_seconds: float,
    poll_interval: float,
):
    """Submit a small US budget-window batch and verify the aggregated shape."""

    timeout = settings.timeout_in_millis / 1000
    payload = {
        "country": "us",
        "version": us_model_version,
        "region": "us",
        "scope": "macro",
        "reform": {
            "gov.irs.credits.ctc.refundable.fully_refundable": {
                "2023-01-01.2100-12-31": True
            }
        },
        "subsample": 200,
        "data": "gs://policyengine-us-data/enhanced_cps_2024.h5",
        "start_year": "2026",
        "window_size": 2,
        "max_parallel": 2,
        "target": "general",
    }

    with httpx.Client(
        base_url=settings.base_url,
        headers=_httpx_headers(),
        timeout=timeout,
    ) as client:
        submit_response = client.post("/simulate/economy/budget-window", json=payload)

    assert submit_response.status_code == HTTPStatus.OK, submit_response.text
    submit_body = submit_response.json()
    assert submit_body["status"] == "submitted"
    assert submit_body["version"] == us_model_version
    assert submit_body["poll_url"].startswith("/budget-window-jobs/")
    batch_job_id = submit_body["batch_job_id"]

    result = poll_for_budget_window_completion(
        batch_job_id=batch_job_id,
        max_wait_seconds=max_wait_seconds,
        poll_interval=poll_interval,
    )

    assert result["status"] == "complete"
    assert result["progress"] == 100
    assert result["completed_years"] == ["2026", "2027"]
    assert result["running_years"] == []
    assert result["queued_years"] == []

    budget_window = result["result"]
    assert budget_window["kind"] == "budgetWindow"
    assert budget_window["startYear"] == "2026"
    assert budget_window["endYear"] == "2027"
    assert budget_window["windowSize"] == 2
    assert [row["year"] for row in budget_window["annualImpacts"]] == [
        "2026",
        "2027",
    ]

    totals = budget_window["totals"]
    assert totals["year"] == "Total"
    assert isinstance(totals["taxRevenueImpact"], int | float)
    assert isinstance(totals["federalTaxRevenueImpact"], int | float)
    assert isinstance(totals["stateTaxRevenueImpact"], int | float)
    assert isinstance(totals["benefitSpendingImpact"], int | float)
    assert isinstance(totals["budgetaryImpact"], int | float)
