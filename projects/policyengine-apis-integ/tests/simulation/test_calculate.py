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


@pytest.mark.beta_only
@pytest.mark.slow
def test_calculate_national_with_breakdowns(
    client: Client | AuthenticatedClient,
    poll_interval: float,
):
    """
    Given a US simulation request with data="national-with-breakdowns"
    When the simulation is submitted and polled to completion
    Then the result contains:
    - Standard economic impact data from national ECPS simulation
    - Congressional district breakdowns aggregated from all 51 state simulations

    Note: This test runs 52 parallel simulations and may take 15-30 minutes.
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
            "data": "national-with-breakdowns",
            "subsample": 200,  # Reduce households to speed up test
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

    # When - poll for completion (extended timeout for 52 parallel simulations)
    # 30 minutes should be sufficient even with cold starts
    max_wait_for_national = 30 * 60  # 30 minutes
    result = poll_for_completion(client, job_id, max_wait_for_national, poll_interval)

    # Then - verify result structure
    assert result.status == "complete"
    assert result.result is not None

    economy_result = result.result

    # Verify standard economic impact sections are present (from national ECPS)
    assert "budget" in economy_result, (
        f"Missing 'budget' in result: {economy_result.keys()}"
    )
    assert "poverty" in economy_result, (
        f"Missing 'poverty' in result: {economy_result.keys()}"
    )
    assert "inequality" in economy_result, (
        f"Missing 'inequality' in result: {economy_result.keys()}"
    )

    # Verify congressional district breakdown is present (aggregated from states)
    assert "congressional_district_impact" in economy_result, (
        f"Missing 'congressional_district_impact' in result: {economy_result.keys()}"
    )

    district_impact = economy_result["congressional_district_impact"]
    assert "districts" in district_impact, (
        f"Missing 'districts' in congressional_district_impact: {district_impact.keys()}"
    )

    districts = district_impact["districts"]

    # Should have ~436 districts (435 congressional + DC)
    assert len(districts) >= 400, f"Expected ~436 districts, got {len(districts)}"

    # Verify district structure
    if districts:
        sample_district = districts[0]
        assert "district" in sample_district, (
            f"Missing 'district' field in district data: {sample_district.keys()}"
        )
        assert "average_household_income_change" in sample_district, (
            f"Missing 'average_household_income_change' in district: {sample_district.keys()}"
        )
        assert "relative_household_income_change" in sample_district, (
            f"Missing 'relative_household_income_change' in district: {sample_district.keys()}"
        )

        # Verify district naming format (e.g., "AL-01", "CA-52")
        district_name = sample_district["district"]
        assert "-" in district_name, (
            f"District name should contain hyphen: {district_name}"
        )


@pytest.mark.beta_only
def test__given_national_with_breakdowns_test__then_returns_district_data(
    client: Client | AuthenticatedClient,
    poll_interval: float,
):
    """
    Given a US simulation request with data="national-with-breakdowns-test"
    When the simulation is submitted and polled to completion
    Then the result contains:
    - Standard economic impact data from national ECPS simulation
    - Congressional district breakdowns from 10 test states

    This uses the test variant that runs only 10 states instead of all 51,
    making it suitable for CI/CD pipelines.

    Expected districts from test states:
    NV(4) + TX(38) + NY(26) + FL(28) + OH(15) + GA(14) + MA(9) + NH(2) + VT(1) + MT(2) = 139
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
            "data": "national-with-breakdowns-test",
            "subsample": 200,  # Reduce households to speed up test
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

    # When - poll for completion (10 states should complete in ~10-15 minutes)
    max_wait_for_test = 20 * 60  # 20 minutes
    result = poll_for_completion(client, job_id, max_wait_for_test, poll_interval)

    # Then - verify result structure
    assert result.status == "complete"
    assert result.result is not None

    economy_result = result.result

    # Verify standard economic impact sections are present (from national ECPS)
    assert "budget" in economy_result, (
        f"Missing 'budget' in result: {economy_result.keys()}"
    )
    assert "poverty" in economy_result, (
        f"Missing 'poverty' in result: {economy_result.keys()}"
    )
    assert "inequality" in economy_result, (
        f"Missing 'inequality' in result: {economy_result.keys()}"
    )

    # Verify congressional district breakdown is present
    assert "congressional_district_impact" in economy_result, (
        f"Missing 'congressional_district_impact' in result: {economy_result.keys()}"
    )

    district_impact = economy_result["congressional_district_impact"]
    assert "districts" in district_impact, (
        f"Missing 'districts' in congressional_district_impact: {district_impact.keys()}"
    )
    assert "successful_states" in district_impact, (
        f"Missing 'successful_states' in congressional_district_impact"
    )

    districts = district_impact["districts"]
    successful_states = district_impact["successful_states"]

    # Should have ~139 districts from 10 test states
    assert len(districts) >= 100, (
        f"Expected ~139 districts from 10 states, got {len(districts)}"
    )
    assert len(successful_states) == 10, (
        f"Expected 10 successful states, got {len(successful_states)}"
    )

    # Verify district structure
    if districts:
        sample_district = districts[0]
        assert "district" in sample_district, (
            f"Missing 'district' field in district data: {sample_district.keys()}"
        )
        assert "average_household_income_change" in sample_district, (
            f"Missing 'average_household_income_change' in district"
        )
        assert "relative_household_income_change" in sample_district, (
            f"Missing 'relative_household_income_change' in district"
        )

        # Verify district naming format (e.g., "TX-01", "NY-26")
        district_name = sample_district["district"]
        assert "-" in district_name, (
            f"District name should contain hyphen: {district_name}"
        )


@pytest.mark.beta_only
def test__given_national_with_breakdowns_for_uk__then_returns_400(
    client: Client | AuthenticatedClient,
):
    """
    Given a UK simulation request with data="national-with-breakdowns"
    When the simulation is submitted
    Then the request is rejected with a 400 error.
    """
    # Given
    request = SimulationRequest.from_dict(
        {
            "country": "uk",
            "scope": "macro",
            "reform": {
                "gov.hmrc.income_tax.rates.uk[0].rate": {"2023-01-01.2100-12-31": 0.21}
            },
            "data": "national-with-breakdowns",
        }
    )

    # When - submit job
    response = submit_simulation_simulate_economy_comparison_post.sync_detailed(
        client=client, body=request
    )

    # Then - should be rejected
    assert response.status_code == HTTPStatus.BAD_REQUEST, (
        f"Expected 400 for UK national-with-breakdowns, got {response.status_code}"
    )


@pytest.mark.beta_only
def test__given_national_with_breakdowns_test_for_uk__then_returns_400(
    client: Client | AuthenticatedClient,
):
    """
    Given a UK simulation request with data="national-with-breakdowns-test"
    When the simulation is submitted
    Then the request is rejected with a 400 error.
    """
    # Given
    request = SimulationRequest.from_dict(
        {
            "country": "uk",
            "scope": "macro",
            "reform": {
                "gov.hmrc.income_tax.rates.uk[0].rate": {"2023-01-01.2100-12-31": 0.21}
            },
            "data": "national-with-breakdowns-test",
        }
    )

    # When - submit job
    response = submit_simulation_simulate_economy_comparison_post.sync_detailed(
        client=client, body=request
    )

    # Then - should be rejected
    assert response.status_code == HTTPStatus.BAD_REQUEST, (
        f"Expected 400 for UK national-with-breakdowns-test, got {response.status_code}"
    )
