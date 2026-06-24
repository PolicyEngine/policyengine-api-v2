"""Tests for the Modal routing-state publisher."""

from __future__ import annotations

import sys

import pytest

from src.modal.utils import update_version_registry as registry


class FakeDict:
    def __init__(self, initial: dict | None = None):
        self._data = dict(initial or {})

    def __getitem__(self, key):
        return self._data[key]

    def __setitem__(self, key, value):
        self._data[key] = value

    def get(self, key, default=None):
        return self._data.get(key, default)

    def snapshot(self) -> dict:
        return dict(self._data)


@pytest.fixture
def patched_modal(monkeypatch):
    stores: dict[str, FakeDict] = {}

    class _Dict:
        @staticmethod
        def from_name(
            name: str,
            environment_name: str,
            create_if_missing: bool,
        ):
            key = f"{environment_name}/{name}"
            if key not in stores:
                if not create_if_missing:
                    raise KeyError(key)
                stores[key] = FakeDict()
            return stores[key]

    class _Modal:
        Dict = _Dict

    monkeypatch.setattr(registry, "modal", _Modal)
    return stores


@pytest.fixture
def fake_bundle_metadata(monkeypatch):
    def fake_country_bundle_metadata(
        country: str,
    ) -> registry.CountryBundleMetadata:
        return {
            "country": country,
            "model_package_name": (
                "policyengine-us" if country == "us" else "policyengine-uk"
            ),
            "model_version": "1.687.0" if country == "us" else "2.88.14",
            "data_package_name": "populace-data",
            "data_version": (
                "populace-us-build" if country == "us" else "populace-uk-build"
            ),
            "data_artifact_revision": (
                "populace-us-build" if country == "us" else "populace-uk-build"
            ),
            "default_dataset": (
                "populace_us_2024" if country == "us" else "populace_uk_2023"
            ),
            "default_dataset_uri": f"hf://datasets/policyengine/{country}/default",
            "dataset_uris": {"default": f"hf://datasets/policyengine/{country}"},
            "dataset_repo_types": {"default": "dataset"},
            "dataset_aliases": {"alias": "default"},
        }

    monkeypatch.setattr(
        registry, "_country_bundle_metadata", fake_country_bundle_metadata
    )


def test__is_newer_version__advances_on_higher_minor():
    assert registry._is_newer_version("1.501.0", "1.500.0") is True


def test__is_newer_version__does_not_advance_on_lower_minor():
    assert registry._is_newer_version("1.499.0", "1.500.0") is False


def test__is_newer_version__advances_when_current_missing():
    assert registry._is_newer_version("1.500.0", None) is True


def test__is_newer_version__does_not_advance_on_equal():
    assert registry._is_newer_version("1.500.0", "1.500.0") is False


def test_validate_routing_state_accepts_complete_state(fake_bundle_metadata):
    state = registry.build_next_routing_state(
        current_state=None,
        app_name="policyengine-simulation-py4-19-1",
        policyengine_version="4.19.1",
        us_version="1.687.0",
        uk_version="2.88.14",
    )

    registry.validate_routing_state(state)


def test_validate_routing_state_rejects_missing_latest_route(fake_bundle_metadata):
    state = registry.build_next_routing_state(
        current_state=None,
        app_name="policyengine-simulation-py4-19-1",
        policyengine_version="4.19.1",
        us_version="1.687.0",
        uk_version="2.88.14",
    )
    state["routes"]["us"].pop("1.687.0")

    with pytest.raises(ValueError, match="latest.us"):
        registry.validate_routing_state(state)


def test_validate_routing_state_rejects_policyengine_route_without_bundle(
    fake_bundle_metadata,
):
    state = registry.build_next_routing_state(
        current_state=None,
        app_name="policyengine-simulation-py4-19-1",
        policyengine_version="4.19.1",
        us_version="1.687.0",
        uk_version="2.88.14",
    )
    state["bundles"].pop("4.19.1")

    with pytest.raises(ValueError, match="no bundle manifest"):
        registry.validate_routing_state(state)


def test_build_next_routing_state_preserves_existing_routes(fake_bundle_metadata):
    current_state = registry.build_next_routing_state(
        current_state=None,
        app_name="policyengine-simulation-py4-18-0",
        policyengine_version="4.18.0",
        us_version="1.687.0",
        uk_version="2.88.14",
    )

    next_state = registry.build_next_routing_state(
        current_state=current_state,
        app_name="policyengine-simulation-py4-19-1",
        policyengine_version="4.19.1",
        us_version="1.687.0",
        uk_version="2.88.14",
    )

    assert (
        next_state["routes"]["policyengine"]["4.18.0"]
        == "policyengine-simulation-py4-18-0"
    )
    assert (
        next_state["routes"]["policyengine"]["4.19.1"]
        == "policyengine-simulation-py4-19-1"
    )
    assert next_state["latest"]["policyengine"] == "4.19.1"
    assert next_state["latest"]["us"] == "1.687.0"


def test_build_next_routing_state_keeps_existing_latest_when_incoming_older(
    fake_bundle_metadata,
):
    current_state = registry.build_next_routing_state(
        current_state=None,
        app_name="policyengine-simulation-py4-19-1",
        policyengine_version="4.19.1",
        us_version="1.687.0",
        uk_version="2.88.14",
    )

    next_state = registry.build_next_routing_state(
        current_state=current_state,
        app_name="policyengine-simulation-py4-18-0",
        policyengine_version="4.18.0",
        us_version="1.687.0",
        uk_version="2.88.14",
    )

    assert next_state["latest"]["policyengine"] == "4.19.1"
    assert (
        next_state["routes"]["policyengine"]["4.18.0"]
        == "policyengine-simulation-py4-18-0"
    )


def test_build_next_routing_state_force_latest_allows_downgrade(
    fake_bundle_metadata,
):
    current_state = registry.build_next_routing_state(
        current_state=None,
        app_name="policyengine-simulation-py4-19-1",
        policyengine_version="4.19.1",
        us_version="1.687.0",
        uk_version="2.88.14",
    )

    next_state = registry.build_next_routing_state(
        current_state=current_state,
        app_name="policyengine-simulation-py4-18-0",
        policyengine_version="4.18.0",
        us_version="1.687.0",
        uk_version="2.88.14",
        force_latest=True,
    )

    assert next_state["latest"]["policyengine"] == "4.18.0"


def test_build_next_routing_state_rejects_country_version_mismatch(
    fake_bundle_metadata,
):
    with pytest.raises(ValueError, match="US version"):
        registry.build_next_routing_state(
            current_state=None,
            app_name="policyengine-simulation-py4-19-1",
            policyengine_version="4.19.1",
            us_version="1.999.0",
            uk_version="2.88.14",
        )


def test_publish_routing_state_writes_only_active_snapshot(
    patched_modal,
    fake_bundle_metadata,
):
    registry.publish_routing_state(
        environment="main",
        app_name="policyengine-simulation-py4-19-1",
        policyengine_version="4.19.1",
        us_version="1.687.0",
        uk_version="2.88.14",
    )

    assert set(patched_modal) == {"main/simulation-api-routing-state"}
    snapshot = patched_modal["main/simulation-api-routing-state"].snapshot()
    active = snapshot["active"]
    assert (
        active["routes"]["policyengine"]["4.19.1"] == "policyengine-simulation-py4-19-1"
    )
    assert active["routes"]["us"]["1.687.0"] == "policyengine-simulation-py4-19-1"
    assert active["bundles"]["4.19.1"]["us"]["dataset_aliases"] == {"alias": "default"}


def test_main_publishes_routing_state(
    patched_modal,
    fake_bundle_metadata,
    monkeypatch,
):
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "update_version_registry",
            "--app-name",
            "policyengine-simulation-py4-19-1",
            "--policyengine-version",
            "4.19.1",
            "--us-version",
            "1.687.0",
            "--uk-version",
            "2.88.14",
            "--environment",
            "main",
        ],
    )

    registry.main()

    active = patched_modal["main/simulation-api-routing-state"].snapshot()["active"]
    assert active["latest"]["policyengine"] == "4.19.1"
    assert active["latest"]["us"] == "1.687.0"
    assert active["latest"]["uk"] == "2.88.14"
