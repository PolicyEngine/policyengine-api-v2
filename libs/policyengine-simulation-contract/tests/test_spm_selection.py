"""Partial public selections inherit pinned bundle defaults before validation."""

import pytest

from policyengine_simulation_contract.gateway_models import SimulationRequest
from policyengine_simulation_contract.spm import SPMInputError, resolve_spm_selection


def resolve(selection, *, kind="metro", area="35620"):
    return resolve_spm_selection(
        "us",
        selection,
        capability={
            "defaults": {
                "forecast_content_sha256": "a" * 64,
                "scenario": "ce_trend",
                "geography_kind": kind,
                "geography_id": area,
            },
        },
        policyengine_version="5.3.0",
        model_version="1.824.7",
    )


def test_partial_area_override_inherits_metro_default_through_request():
    request = SimulationRequest(country="us", spm={"geography_id": "31080"})
    payload = request.model_dump(mode="json")["spm"]
    assert payload == {"geography_id": "31080"}
    resolved = resolve(payload)
    assert resolved["geography_kind"] == "metro"
    assert resolved["geography_id"] == "31080"


@pytest.mark.parametrize("kind", ["county", "national"])
def test_partial_area_override_rejects_incompatible_defaults(kind):
    with pytest.raises(SPMInputError) as error:
        resolve({"geography_id": "31080"}, kind=kind, area=None)
    assert error.value.code == "SPM_SETTINGS_INVALID"


def test_explicit_metro_inherits_area_only_from_metro_defaults():
    assert resolve({"geography_kind": "metro"})["geography_id"] == "35620"
    with pytest.raises(SPMInputError) as error:
        resolve({"geography_kind": "metro"}, kind="county", area=None)
    assert error.value.code == "SPM_SETTINGS_INVALID"


def test_explicit_national_discards_default_metro_area():
    resolved = resolve({"geography_kind": "national"})
    assert resolved["geography_kind"] == "national"
    assert resolved["geography_id"] is None


@pytest.mark.parametrize(
    "provenance,wrapper,model,accepted",
    [
        ("legacy-country-dict", None, "1.500.0", True),
        ("legacy-seed", None, "1.715.2", True),
        ("legacy-seed", None, "1.764.6", True),
        (None, None, "1.715.2", False),
        ("unknown", None, "1.715.2", False),
        ("legacy-seed", None, "1.764.7", False),
        ("legacy-seed", None, "unknown", False),
        ("legacy-country-dict", "5.3.1", "1.715.2", False),
    ],
)
def test_legacy_allowance_requires_route_provenance_and_historical_model(
    provenance, wrapper, model, accepted
):
    kwargs = dict(
        capability=None,
        policyengine_version=wrapper,
        model_version=model,
        route_provenance=provenance,
    )
    if accepted:
        assert resolve_spm_selection("us", None, **kwargs) is None
    else:
        with pytest.raises(SPMInputError) as error:
            resolve_spm_selection("us", None, **kwargs)
        assert error.value.code == "SPM_CONFIGURATION_UNAVAILABLE"
    for selection in ({}, {"geography_kind": "national"}):
        with pytest.raises(SPMInputError) as error:
            resolve_spm_selection("us", selection, **kwargs)
        assert error.value.code == "SPM_CONFIGURATION_UNAVAILABLE"
