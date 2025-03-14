import json
from fastapi.testclient import TestClient
from copy import deepcopy
from ...fixtures.routers.calculate import client, mock_calculate_method
from policyengine_api.api.data.examples.example_household import (
    example_household_output_us,
    example_household_input_us,
)


valid_country_id = "us"
valid_household_input = {"household": deepcopy(example_household_input_us)}


def test_given_valid_input__return_valid_output(
    client: TestClient, mock_calculate_method
):

    response = client.post(
        f"/{valid_country_id}/calculate", json=valid_household_input
    )
    assert response.status_code == 200
    assert response.json() == example_household_output_us


def test_given_invalid_country_id__return_error(client: TestClient):
    invalid_country_id = "invalid"

    response = client.post(
        f"/{invalid_country_id}/calculate",
        json=json.dumps(example_household_input_us),
    )
    assert response.status_code == 422
    assert "Input should be 'us', 'uk'," in response.json()["detail"][0]["msg"]


# Given invalid household input, return validation error
def test_given_invalid_household_input__return_validation_error(
    client: TestClient,
):
    invalid_household_input = {}
    valid_country_id = "us"

    response = client.post(
        f"/{valid_country_id}/calculate",
        json=json.dumps(invalid_household_input),
    )
    assert response.status_code == 422
    assert "Field required" in response.json()["detail"][0]["msg"]
