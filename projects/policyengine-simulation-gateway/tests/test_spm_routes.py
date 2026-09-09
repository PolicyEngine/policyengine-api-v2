"""SPM capability resolution on historical and ambiguous registry routes."""

from copy import deepcopy

import pytest

from fixtures.gateway_endpoints import TEST_ROUTING_STATE


CAPABILITY = {
    "contract_version": "canonical-spm-v1",
    "defaults": {"forecast_content_sha256": "a" * 64, "scenario": "ce_trend"},
}
ENDPOINTS = [
    ("/simulate/economy/comparison", {"scope": "macro"}),
    (
        "/simulate/economy/budget-window",
        {"region": "us", "start_year": "2026", "window_size": 2},
    ),
]


def legacy_route(mock_modal, source, model_version):
    app_name = "policyengine-simulation-us1-715-2-uk2-88-20"
    if source == "legacy-country-dict":
        app_name = "legacy-app"
        del mock_modal["dicts"]["simulation-api-routing-state"]
        mock_modal["dicts"]["simulation-api-us-versions"] = {
            "latest": model_version,
            model_version: app_name,
        }
    else:
        mock_modal["dicts"]["simulation-api-routing-state"] = {
            "active": {
                "schema_version": 1,
                "generation": source,
                "latest": {"us": model_version},
                "routes": {"policyengine": {}, "us": {model_version: app_name}},
                "bundles": {},
            }
        }


@pytest.mark.parametrize("endpoint,extra", ENDPOINTS)
@pytest.mark.parametrize("source", ["legacy-country-dict", "legacy-seed"])
@pytest.mark.parametrize("version", [None, "1.715.2"])
def test_historical_no_wrapper_route_submits_without_spm(
    mock_modal, client, endpoint, extra, source, version
):
    legacy_route(mock_modal, source, "1.715.2")
    response = client.post(
        endpoint, json={"country": "us", "version": version, **extra}
    )
    assert response.status_code == 200, response.text
    assert "spm" not in mock_modal["func"].last_payload
    assert response.json()["policyengine_bundle"]["model_version"] == "1.715.2"
    assert "policyengine_version" not in response.json()["policyengine_bundle"]


@pytest.mark.parametrize("endpoint,extra", ENDPOINTS)
@pytest.mark.parametrize("source", ["legacy-country-dict", "legacy-seed"])
@pytest.mark.parametrize("selection", [{}, {"geography_kind": "national"}])
def test_historical_route_rejects_any_explicit_spm(
    mock_modal, client, endpoint, extra, source, selection
):
    legacy_route(mock_modal, source, "1.715.2")
    response = client.post(endpoint, json={"country": "us", "spm": selection, **extra})
    assert response.status_code == 400
    assert response.json()["errors"][0]["code"] == "SPM_CONFIGURATION_UNAVAILABLE"
    assert mock_modal["func"].calls == []


@pytest.mark.parametrize("endpoint,extra", ENDPOINTS)
@pytest.mark.parametrize(
    "source,model_version",
    [
        ("legacy-country-dict", "1.824.7"),
        ("legacy-seed", "1.824.7"),
        ("legacy-seed", "future-model"),
        ("unknown-generation", "1.715.2"),
    ],
)
def test_missing_wrapper_does_not_certify_unknown_routes(
    mock_modal, client, endpoint, extra, source, model_version
):
    legacy_route(mock_modal, source, model_version)
    response = client.post(endpoint, json={"country": "us", **extra})
    assert response.status_code == 400
    assert response.json()["errors"][0]["code"] == "SPM_CONFIGURATION_UNAVAILABLE"
    assert mock_modal["func"].calls == []


@pytest.mark.parametrize("endpoint,extra", ENDPOINTS)
def test_legacy_seed_cannot_erase_future_wrapper_from_app_name(
    mock_modal, client, endpoint, extra
):
    legacy_route(mock_modal, "legacy-seed", "1.715.2")
    state = mock_modal["dicts"]["simulation-api-routing-state"]["active"]
    state["routes"]["us"]["1.715.2"] = "policyengine-simulation-py99-0-0"
    response = client.post(endpoint, json={"country": "us", **extra})
    assert response.status_code == 400
    assert response.json()["errors"][0]["code"] == "SPM_CONFIGURATION_UNAVAILABLE"
    assert mock_modal["func"].calls == []


@pytest.mark.parametrize("schema_version", [None, 2])
def test_legacy_seed_requires_supported_registry_schema(
    mock_modal, client, schema_version
):
    legacy_route(mock_modal, "legacy-seed", "1.715.2")
    state = mock_modal["dicts"]["simulation-api-routing-state"]["active"]
    state["schema_version"] = schema_version
    response = client.post("/simulate/economy/comparison", json={"country": "us"})
    assert response.status_code == 400
    assert response.json()["errors"][0]["code"] == "SPM_CONFIGURATION_UNAVAILABLE"
    assert mock_modal["func"].calls == []


def shared_app_state(mock_modal, *, sibling_model):
    state = deepcopy(TEST_ROUTING_STATE)
    original = state["bundles"]["4.10.0"]
    app_name = original["app_name"]
    state["routes"]["policyengine"]["5.3.0"] = app_name
    state["bundles"]["5.3.0"] = {
        **deepcopy(original),
        "policyengine_version": "5.3.0",
        "us": {**original["us"], "model_version": sibling_model},
        "spm": deepcopy(CAPABILITY),
    }
    state["routes"]["us"][sibling_model] = app_name
    mock_modal["dicts"]["simulation-api-routing-state"] = {"active": state}
    return state


@pytest.mark.parametrize("endpoint,extra", ENDPOINTS)
def test_shared_app_resolves_unique_country_model_bundle(
    mock_modal, client, endpoint, extra
):
    shared_app_state(mock_modal, sibling_model="1.824.7")
    response = client.post(
        endpoint, json={"country": "us", "version": "1.824.7", **extra}
    )
    assert response.status_code == 200, response.text
    assert response.json()["policyengine_bundle"]["policyengine_version"] == "5.3.0"
    assert mock_modal["func"].last_payload["spm"]["scenario"] == "ce_trend"


def test_latest_route_alias_does_not_create_ambiguous_bundle(mock_modal, client):
    state = shared_app_state(mock_modal, sibling_model="1.824.7")
    state["routes"]["policyengine"]["latest"] = state["routes"]["policyengine"]["5.3.0"]
    response = client.post(
        "/simulate/economy/comparison", json={"country": "us", "version": "1.824.7"}
    )
    assert response.status_code == 200
    assert response.json()["policyengine_bundle"]["policyengine_version"] == "5.3.0"


@pytest.mark.parametrize("endpoint,extra", ENDPOINTS)
def test_shared_app_with_ambiguous_country_model_requires_explicit_bundle(
    mock_modal, client, endpoint, extra
):
    shared_app_state(mock_modal, sibling_model="1.500.0")
    response = client.post(
        endpoint, json={"country": "us", "version": "1.500.0", **extra}
    )
    assert response.status_code == 400
    assert "policyengine_version" in response.json()["detail"]
    assert mock_modal["func"].calls == []
    explicit = client.post(
        endpoint,
        json={"country": "us", "policyengine_version": "5.3.0", **extra},
    )
    assert explicit.status_code == 200
    assert mock_modal["func"].last_payload["spm"]["scenario"] == "ce_trend"


@pytest.mark.parametrize("endpoint,extra", ENDPOINTS)
@pytest.mark.parametrize("sibling_model", [None, "", "   ", 42])
def test_shared_app_with_missing_model_metadata_is_ambiguous(
    mock_modal, client, endpoint, extra, sibling_model
):
    state = shared_app_state(mock_modal, sibling_model="1.824.7")
    state["bundles"]["4.10.0"]["us"]["model_version"] = sibling_model
    response = client.post(
        endpoint, json={"country": "us", "version": "1.824.7", **extra}
    )
    assert response.status_code == 400
    assert "policyengine_version" in response.json()["detail"]
    assert mock_modal["func"].calls == []


@pytest.mark.parametrize(
    "invalid_capability",
    [
        {"contract_version": "canonical-spm-v1", "defaults": {"scenario": "ce_trend"}},
        {**CAPABILITY, "contract_version": "unknown-contract"},
        {**CAPABILITY, "undeclared": True},
        {"defaults": {**CAPABILITY["defaults"], "geography_kind": "metro"}},
    ],
)
def test_versions_omits_malformed_capability_and_submission_rejects_it(
    mock_modal, client, invalid_capability
):
    state = shared_app_state(mock_modal, sibling_model="1.824.7")
    state["bundles"]["4.10.0"]["spm"] = invalid_capability
    response = client.get("/versions")
    assert response.status_code == 200
    assert set(response.json()["spm_capabilities"]) == {"5.3.0"}
    rejected = client.post(
        "/simulate/economy/comparison",
        json={"country": "us", "policyengine_version": "4.10.0"},
    )
    assert rejected.status_code == 400
    assert rejected.json()["errors"][0]["code"] == "SPM_CONFIGURATION_UNAVAILABLE"
    assert mock_modal["func"].calls == []
