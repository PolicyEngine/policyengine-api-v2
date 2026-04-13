"""
Integration tests for Modal-based simulation calculations.

These tests run against the staging Modal deployment and verify
that economy-wide simulations complete successfully.
"""

import time
from http import HTTPStatus

import pytest

from policyengine_api_simulation_client import AuthenticatedClient, Client
from policyengine_api_simulation_client.api.default import (
    get_job_status_jobs_job_id_get,
    submit_simulation_simulate_economy_comparison_post,
)
from policyengine_api_simulation_client.models import (
    JobStatusResponse,
    JobSubmitResponse,
    SimulationRequest,
)


def poll_for_completion(
    client: Client | AuthenticatedClient,
    job_id: str,
    max_wait_seconds: float,
    poll_interval: float,
) -> JobStatusResponse:
    """
    Poll for job completion.

    Args:
        client: The API client
        job_id: The job ID to poll
        max_wait_seconds: Maximum time to wait for completion
        poll_interval: Time between polls in seconds

    Returns:
        The final JobStatusResponse

    Raises:
        TimeoutError: If job doesn't complete within max_wait_seconds
        AssertionError: If job fails
    """
    start_time = time.time()

    while time.time() - start_time < max_wait_seconds:
        response = get_job_status_jobs_job_id_get.sync_detailed(
            job_id=job_id, client=client
        )

        if response.status_code == HTTPStatus.OK:
            assert isinstance(response.parsed, JobStatusResponse)
            assert response.parsed.status == "complete", (
                f"Unexpected status: {response.parsed}"
            )
            return response.parsed

        if response.status_code == HTTPStatus.INTERNAL_SERVER_ERROR:
            raise AssertionError(f"Job failed: {response.content}")

        if response.status_code == HTTPStatus.ACCEPTED:
            # Still running, wait and retry
            time.sleep(poll_interval)
            continue

        # Unexpected status code
        raise AssertionError(f"Unexpected status code: {response.status_code}")

    raise TimeoutError(f"Job {job_id} did not complete within {max_wait_seconds}s")


@pytest.mark.beta_only
def test_calculate_default_model(
    client: Client | AuthenticatedClient,
    max_wait_seconds: float,
    poll_interval: float,
):
    """
    Given a simulation request with default model version
    When the simulation is submitted and polled to completion
    Then the result contains expected economic impact data.
    """
    # Given
    request = SimulationRequest.from_dict(
        {
            "country": "us",
            "scope": "macro",
            "reform": {
                "gov.irs.credits.ctc.refundable.fully_refundable": {
                    "2023-01-01.2100-12-31": True
                }
            },
            "subsample": 200,  # Reduce households to speed up test
            "data": "gs://policyengine-us-data/enhanced_cps_2024.h5",
        }
    )

    # When - submit job
    submit_response = submit_simulation_simulate_economy_comparison_post.sync(
        client=client, body=request
    )
    assert isinstance(submit_response, JobSubmitResponse), (
        f"Unexpected response type: {type(submit_response)}"
    )
    job_id = submit_response.job_id

    # When - poll for completion
    result = poll_for_completion(client, job_id, max_wait_seconds, poll_interval)

    # Then - verify result structure
    assert result.status == "complete"
    assert result.result is not None

    # Verify key economic impact sections are present
    economy_result = result.result
    assert "budget" in economy_result, (
        f"Missing 'budget' in result: {economy_result.keys()}"
    )
    assert "poverty" in economy_result, (
        f"Missing 'poverty' in result: {economy_result.keys()}"
    )
    assert "inequality" in economy_result, (
        f"Missing 'inequality' in result: {economy_result.keys()}"
    )


@pytest.mark.beta_only
def test_calculate_specific_model(
    client: Client | AuthenticatedClient,
    us_model_version: str,
    max_wait_seconds: float,
    poll_interval: float,
):
    """
    Given a simulation request with a specific model version
    When the simulation is submitted and polled to completion
    Then the result contains expected economic impact data.
    """
    # Given
    request = SimulationRequest.from_dict(
        {
            "country": "us",
            "version": us_model_version,
            "scope": "macro",
            "reform": {
                "gov.irs.credits.ctc.refundable.fully_refundable": {
                    "2023-01-01.2100-12-31": True
                }
            },
            "subsample": 200,
            "data": "gs://policyengine-us-data/enhanced_cps_2024.h5",
        }
    )

    # When - submit job
    submit_response = submit_simulation_simulate_economy_comparison_post.sync(
        client=client, body=request
    )
    assert isinstance(submit_response, JobSubmitResponse), (
        f"Unexpected response type: {type(submit_response)}"
    )
    assert submit_response.version == us_model_version, (
        f"Version mismatch: expected {us_model_version}, got {submit_response.version}"
    )
    job_id = submit_response.job_id

    # When - poll for completion
    result = poll_for_completion(client, job_id, max_wait_seconds, poll_interval)

    # Then - verify result structure
    assert result.status == "complete"
    assert result.result is not None

    economy_result = result.result
    assert "budget" in economy_result
    assert "poverty" in economy_result
    assert "inequality" in economy_result


@pytest.mark.beta_only
def test_calculate_uk_model(
    client: Client | AuthenticatedClient,
    max_wait_seconds: float,
    poll_interval: float,
):
    """
    Given a UK simulation request
    When the simulation is submitted and polled to completion
    Then the result contains expected economic impact data.
    """
    # Given
    request = SimulationRequest.from_dict(
        {
            "country": "uk",
            "scope": "macro",
            "reform": {
                "gov.hmrc.income_tax.rates.uk[0].rate": {"2023-01-01.2100-12-31": 0.21}
            },
            # No subsample - UKMultiYearDataset lacks .name attribute required by subsample method
        }
    )

    # When - submit job
    submit_response = submit_simulation_simulate_economy_comparison_post.sync(
        client=client, body=request
    )
    assert isinstance(submit_response, JobSubmitResponse), (
        f"Unexpected response type: {type(submit_response)}"
    )
    job_id = submit_response.job_id

    # When - poll for completion
    result = poll_for_completion(client, job_id, max_wait_seconds, poll_interval)

    # Then - verify result structure
    assert result.status == "complete"
    assert result.result is not None

    economy_result = result.result
    assert "budget" in economy_result
    assert "poverty" in economy_result
    assert "inequality" in economy_result
