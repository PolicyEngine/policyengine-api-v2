"""
Unit tests for gateway endpoints.

Tests verify the endpoint correctly resolves app names and routes
simulation requests.
"""

import pytest
from fastapi.testclient import TestClient

pytest_plugins = ["tests.fixtures.endpoints"]


class TestGetAppName:
    """Tests for the get_app_name helper function."""

    def test__given_us_country_no_version__then_returns_latest_app(self, mock_modal):
        """
        Given country='us' and no version specified
        When get_app_name is called
        Then returns the app name for the 'latest' version.
        """
        from src.modal.gateway.endpoints import get_app_name

        # Given
        mock_modal["dicts"]["simulation-api-us-versions"] = {
            "latest": "1.500.0",
            "1.500.0": "policyengine-simulation-us1-500-0-uk2-66-0",
        }

        # When
        app_name, resolved_version = get_app_name("us", None)

        # Then
        assert resolved_version == "1.500.0"
        assert app_name == "policyengine-simulation-us1-500-0-uk2-66-0"

    def test__given_us_country_with_version__then_returns_specified_app(
        self, mock_modal
    ):
        """
        Given country='us' and a specific version
        When get_app_name is called
        Then returns the app name for that version.
        """
        from src.modal.gateway.endpoints import get_app_name

        # Given
        mock_modal["dicts"]["simulation-api-us-versions"] = {
            "1.459.0": "policyengine-simulation-us1-459-0-uk2-65-9"
        }

        # When
        app_name, resolved_version = get_app_name("us", "1.459.0")

        # Then
        assert resolved_version == "1.459.0"
        assert app_name == "policyengine-simulation-us1-459-0-uk2-65-9"

    def test__given_uk_country__then_uses_uk_version_dict(self, mock_modal):
        """
        Given country='uk'
        When get_app_name is called
        Then uses the UK version dictionary.
        """
        from src.modal.gateway.endpoints import get_app_name

        # Given
        mock_modal["dicts"]["simulation-api-uk-versions"] = {
            "latest": "2.66.0",
            "2.66.0": "policyengine-simulation-us1-500-0-uk2-66-0",
        }

        # When
        app_name, resolved_version = get_app_name("uk", None)

        # Then
        assert resolved_version == "2.66.0"
        assert app_name == "policyengine-simulation-us1-500-0-uk2-66-0"

    def test__given_invalid_country__then_raises_value_error(self):
        """
        Given an invalid country code
        When get_app_name is called
        Then raises ValueError.
        """
        from src.modal.gateway.endpoints import get_app_name

        # When / Then
        with pytest.raises(ValueError, match="Unknown country"):
            get_app_name("invalid", None)

    def test__given_unknown_version__then_raises_value_error(self, mock_modal):
        """
        Given a version not in the registry
        When get_app_name is called
        Then raises ValueError.
        """
        from src.modal.gateway.endpoints import get_app_name

        # Given
        mock_modal["dicts"]["simulation-api-us-versions"] = {"1.459.0": "some-app"}

        # When / Then
        with pytest.raises(ValueError, match="Unknown version"):
            get_app_name("us", "9.9.9")


class TestSubmitSimulationEndpoint:
    """Tests for POST /simulate/economy/comparison endpoint."""

    def test__given_regular_data_value__then_routes_to_run_simulation(
        self, mock_modal, client: TestClient
    ):
        """
        Given a request with a data value
        When the simulation is submitted
        Then routes to run_simulation function.
        """
        # Given
        mock_modal["dicts"]["simulation-api-us-versions"] = {
            "latest": "1.500.0",
            "1.500.0": "policyengine-simulation-us1-500-0-uk2-66-0",
        }

        request_body = {
            "country": "us",
            "scope": "macro",
            "reform": {},
            "data": "gs://policyengine-us-data/enhanced_cps_2024.h5",
        }

        # When
        response = client.post("/simulate/economy/comparison", json=request_body)

        # Then
        assert response.status_code == 200
        assert mock_modal["func"].last_from_name_call == (
            "policyengine-simulation-us1-500-0-uk2-66-0",
            "run_simulation",
        )

    def test__given_no_data_value__then_routes_to_run_simulation(
        self, mock_modal, client: TestClient
    ):
        """
        Given a request with no data field
        When the simulation is submitted
        Then routes to regular run_simulation function.
        """
        # Given
        mock_modal["dicts"]["simulation-api-us-versions"] = {
            "latest": "1.500.0",
            "1.500.0": "policyengine-simulation-us1-500-0-uk2-66-0",
        }

        request_body = {
            "country": "us",
            "scope": "macro",
            "reform": {},
        }

        # When
        response = client.post("/simulate/economy/comparison", json=request_body)

        # Then
        assert response.status_code == 200
        assert mock_modal["func"].last_from_name_call == (
            "policyengine-simulation-us1-500-0-uk2-66-0",
            "run_simulation",
        )

    def test__given_submission__then_returns_job_id_and_poll_url(
        self, mock_modal, client: TestClient
    ):
        """
        Given a simulation submission
        When the request completes
        Then returns job_id and poll_url for async polling.
        """
        # Given
        mock_modal["dicts"]["simulation-api-us-versions"] = {
            "latest": "1.500.0",
            "1.500.0": "policyengine-simulation-us1-500-0-uk2-66-0",
        }

        request_body = {
            "country": "us",
            "scope": "macro",
            "reform": {},
        }

        # When
        response = client.post("/simulate/economy/comparison", json=request_body)

        # Then
        assert response.status_code == 200
        data = response.json()
        assert "job_id" in data
        assert data["job_id"] == "mock-job-id-123"
        assert data["poll_url"] == "/jobs/mock-job-id-123"
        assert data["status"] == "submitted"

    def test__given_submission_with_telemetry__then_preserves_run_id(
        self, mock_modal, client: TestClient
    ):
        """
        Given a simulation submission with internal telemetry metadata
        When the request completes
        Then the spawned payload preserves telemetry and the response echoes run_id.
        """
        mock_modal["dicts"]["simulation-api-us-versions"] = {
            "latest": "1.500.0",
            "1.500.0": "policyengine-simulation-us1-500-0-uk2-66-0",
        }

        request_body = {
            "country": "us",
            "scope": "macro",
            "reform": {},
            "_telemetry": {
                "run_id": "run-123",
                "process_id": "proc-123",
                "capture_mode": "disabled",
            },
        }

        response = client.post("/simulate/economy/comparison", json=request_body)

        assert response.status_code == 200
        data = response.json()
        assert data["run_id"] == "run-123"
        assert mock_modal["func"].last_payload["_telemetry"]["run_id"] == "run-123"
        assert (
            mock_modal["dicts"]["simulation-api-job-telemetry"]["mock-job-id-123"][
                "run_id"
            ]
            == "run-123"
        )


class TestGetJobStatusEndpoint:
    """Tests for GET /jobs/{job_id}."""

    def test__given_running_job__then_returns_running_response_with_run_id(
        self, mock_modal, client: TestClient
    ):
        from tests.fixtures.endpoints import MockFunctionCall

        mock_modal["dicts"]["simulation-api-job-telemetry"] = {
            "mock-job-id-123": {"run_id": "run-123"}
        }
        mock_modal["function_calls"]["mock-job-id-123"] = MockFunctionCall(
            object_id="mock-job-id-123",
            is_running=True,
        )

        response = client.get("/jobs/mock-job-id-123")

        assert response.status_code == 202
        assert response.json() == {
            "status": "running",
            "run_id": "run-123",
            "result": None,
            "error": None,
        }

    def test__given_complete_job__then_returns_result_with_run_id(
        self, mock_modal, client: TestClient
    ):
        from tests.fixtures.endpoints import MockFunctionCall

        mock_modal["dicts"]["simulation-api-job-telemetry"] = {
            "mock-job-id-123": {"run_id": "run-123"}
        }
        mock_modal["function_calls"]["mock-job-id-123"] = MockFunctionCall(
            object_id="mock-job-id-123",
            result={"budget": {"reform": 1200}},
        )

        response = client.get("/jobs/mock-job-id-123")

        assert response.status_code == 200
        assert response.json() == {
            "status": "complete",
            "run_id": "run-123",
            "result": {"budget": {"reform": 1200}},
            "error": None,
        }

    def test__given_failed_job__then_returns_error_with_run_id(
        self, mock_modal, client: TestClient
    ):
        from tests.fixtures.endpoints import MockFunctionCall

        mock_modal["dicts"]["simulation-api-job-telemetry"] = {
            "mock-job-id-123": {"run_id": "run-123"}
        }
        mock_modal["function_calls"]["mock-job-id-123"] = MockFunctionCall(
            object_id="mock-job-id-123",
            error=RuntimeError("Simulation failed"),
        )

        response = client.get("/jobs/mock-job-id-123")

        assert response.status_code == 500
        assert response.json() == {
            "status": "failed",
            "run_id": "run-123",
            "result": None,
            "error": "Simulation failed",
        }


class TestVersionEndpoints:
    def test__list_versions__returns_raw_registries(
        self, mock_modal, client: TestClient
    ):
        mock_modal["dicts"]["simulation-api-us-versions"] = {
            "latest": "1.632.5",
            "1.632.5": "policyengine-simulation-us1-632-5-uk2-78-0",
        }
        mock_modal["dicts"]["simulation-api-uk-versions"] = {
            "latest": "2.78.0",
            "2.78.0": "policyengine-simulation-us1-632-5-uk2-78-0",
        }

        response = client.get("/versions")

        assert response.status_code == 200
        assert response.json() == {
            "us": {
                "latest": "1.632.5",
                "1.632.5": "policyengine-simulation-us1-632-5-uk2-78-0",
            },
            "uk": {
                "latest": "2.78.0",
                "2.78.0": "policyengine-simulation-us1-632-5-uk2-78-0",
            },
        }

    def test__list_version_catalog__returns_normalized_snapshots(
        self, mock_modal, client: TestClient
    ):
        mock_modal["dicts"]["simulation-api-us-versions"] = {
            "latest": "1.632.5",
            "1.606.1": "policyengine-simulation-us1-606-1-uk2-75-2",
            "1.632.5": "policyengine-simulation-us1-632-5-uk2-78-0",
        }
        mock_modal["dicts"]["simulation-api-uk-versions"] = {
            "latest": "2.78.0",
            "2.78.0": "policyengine-simulation-us1-632-5-uk2-78-0",
        }

        response = client.get("/versions/catalog")

        assert response.status_code == 200
        payload = response.json()
        assert payload["us"]["latest_version"] == "1.632.5"
        assert payload["us"]["versions"][0]["country_package_version"] == "1.632.5"
        assert payload["us"]["versions"][0]["is_latest"] is True
        assert payload["uk"]["latest_version"] == "2.78.0"

    def test__get_country_version_catalog__returns_normalized_country_snapshot(
        self, mock_modal, client: TestClient
    ):
        mock_modal["dicts"]["simulation-api-us-versions"] = {
            "latest": "1.632.5",
            "1.632.5": "policyengine-simulation-us1-632-5-uk2-78-0",
        }

        response = client.get("/versions/catalog/us")

        assert response.status_code == 200
        payload = response.json()
        assert payload["country"] == "us"
        assert payload["registry_name"] == "simulation-api-us-versions"
        assert payload["latest_version"] == "1.632.5"
        assert payload["versions"][0]["modal_app_name"].startswith(
            "policyengine-simulation-us1-632-5"
        )

    def test__get_country_version_catalog__rejects_unknown_country(
        self, client: TestClient
    ):
        response = client.get("/versions/catalog/ca")

        assert response.status_code == 404
        assert "Unknown country" in response.json()["detail"]
