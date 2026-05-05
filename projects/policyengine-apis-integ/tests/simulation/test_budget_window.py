"""
Integration tests for Modal-based budget-window batches.

These tests run against the staging Modal deployment and verify that the
gateway can spawn the parent budget-window worker, the parent can spawn child
simulation workers, and the completed batch result has the public response
shape expected by API consumers.
"""

import json
import time
from http import HTTPStatus

import pytest

from policyengine_api_simulation_client import AuthenticatedClient, Client
from policyengine_api_simulation_client.api.default import (
    get_budget_window_job_status_budget_window_jobs_batch_job_id_get,
    submit_budget_window_batch_simulate_economy_budget_window_post,
)
from policyengine_api_simulation_client.models import (
    BudgetWindowBatchRequest,
    BudgetWindowBatchStatusResponse,
    BudgetWindowBatchSubmitResponse,
    BudgetWindowResult,
)
from policyengine_api_simulation_client.types import Unset


def _decode_response_content(content: bytes) -> str:
    try:
        return json.dumps(json.loads(content), sort_keys=True)
    except (json.JSONDecodeError, UnicodeDecodeError):
        return content.decode("utf-8", errors="replace")


def poll_budget_window_batch(
    client: Client | AuthenticatedClient,
    batch_job_id: str,
    max_wait_seconds: float,
    poll_interval: float,
) -> BudgetWindowBatchStatusResponse:
    """
    Poll a budget-window batch until it reaches a terminal state.
    """
    deadline = time.monotonic() + max_wait_seconds
    last_status_code: HTTPStatus | None = None
    last_content = b""

    while time.monotonic() < deadline:
        response = get_budget_window_job_status_budget_window_jobs_batch_job_id_get.sync_detailed(
            batch_job_id=batch_job_id, client=client
        )
        last_status_code = response.status_code
        last_content = response.content

        if response.status_code == HTTPStatus.ACCEPTED:
            time.sleep(poll_interval)
            continue

        if response.status_code == HTTPStatus.OK:
            assert isinstance(response.parsed, BudgetWindowBatchStatusResponse), (
                f"Unexpected response type: {type(response.parsed)}"
            )
            assert response.parsed.status == "complete", (
                f"Unexpected budget-window status: {response.parsed}"
            )
            return response.parsed

        if response.status_code == HTTPStatus.INTERNAL_SERVER_ERROR:
            raise AssertionError(
                "Budget-window batch failed: "
                f"{_decode_response_content(response.content)}"
            )

        raise AssertionError(
            "Unexpected budget-window poll status "
            f"{response.status_code}: {_decode_response_content(response.content)}"
        )

    raise TimeoutError(
        f"Budget-window batch {batch_job_id} did not complete within "
        f"{max_wait_seconds}s; last response was "
        f"{last_status_code}: {_decode_response_content(last_content)}"
    )


@pytest.mark.beta_only
def test_budget_window_multi_year_batch_completes(
    client: Client | AuthenticatedClient,
    us_model_version: str,
    max_wait_seconds: float,
    poll_interval: float,
):
    """
    Given a two-year US budget-window request
    When the batch is submitted and polled to completion
    Then the response contains 2026 and 2027 annual impacts plus totals.
    """
    request = BudgetWindowBatchRequest.from_dict(
        {
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
        }
    )

    submit_response = (
        submit_budget_window_batch_simulate_economy_budget_window_post.sync_detailed(
            client=client,
            body=request,
        )
    )

    assert submit_response.status_code == HTTPStatus.OK, (
        "Unexpected submit status "
        f"{submit_response.status_code}: "
        f"{_decode_response_content(submit_response.content)}"
    )
    assert isinstance(submit_response.parsed, BudgetWindowBatchSubmitResponse), (
        f"Unexpected response type: {type(submit_response.parsed)}"
    )
    assert submit_response.parsed.status == "submitted"
    assert submit_response.parsed.version == us_model_version

    batch_job_id = submit_response.parsed.batch_job_id
    assert submit_response.parsed.poll_url == f"/budget-window-jobs/{batch_job_id}"

    completed = poll_budget_window_batch(
        client=client,
        batch_job_id=batch_job_id,
        max_wait_seconds=max_wait_seconds,
        poll_interval=poll_interval,
    )

    assert completed.status == "complete"
    assert completed.progress == 100
    assert completed.error is None or isinstance(completed.error, Unset)
    assert isinstance(completed.result, BudgetWindowResult)

    result = completed.result
    assert result.kind == "budgetWindow"
    assert result.start_year == "2026"
    assert result.end_year == "2027"
    assert result.window_size == 2
    annual_impacts = result.annual_impacts
    assert not isinstance(annual_impacts, Unset)
    assert [impact.year for impact in annual_impacts] == ["2026", "2027"]
    assert result.totals.year == "Total"
    assert all(
        isinstance(impact.budgetary_impact, int | float) for impact in annual_impacts
    )
