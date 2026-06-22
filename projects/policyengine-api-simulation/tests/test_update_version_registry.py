"""Tests for the Modal version-registry updater."""

from __future__ import annotations

import sys
from copy import deepcopy

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

    def items(self):
        return self._data.items()

    def snapshot(self) -> dict:
        return dict(self._data)


@pytest.fixture
def patched_modal(monkeypatch):
    stores: dict[str, FakeDict] = {}

    class _Dict:
        @staticmethod
        def from_name(name: str, environment_name: str, create_if_missing: bool):
            key = f"{environment_name}/{name}"
            if key not in stores:
                stores[key] = FakeDict()
            return stores[key]

    class _Modal:
        Dict = _Dict

    monkeypatch.setattr(registry, "modal", _Modal)
    return stores


def test__is_newer_version__advances_on_higher_minor():
    assert registry._is_newer_version("1.501.0", "1.500.0") is True


def test__is_newer_version__does_not_advance_on_lower_minor():
    assert registry._is_newer_version("1.499.0", "1.500.0") is False


def test__is_newer_version__advances_when_current_missing():
    assert registry._is_newer_version("1.500.0", None) is True


def test__is_newer_version__does_not_advance_on_equal():
    assert registry._is_newer_version("1.500.0", "1.500.0") is False


def test_update_version_dict__keeps_latest_when_incoming_older(patched_modal):
    stores = patched_modal
    stores["main/simulation-api-us-versions"] = FakeDict(
        {
            "latest": "1.500.0",
            "1.500.0": "policyengine-simulation-py4-10-0",
        }
    )

    registry.update_version_dict(
        "simulation-api-us-versions",
        "main",
        "1.400.0",
        "policyengine-simulation-py3-8-0",
    )

    snapshot = stores["main/simulation-api-us-versions"].snapshot()
    assert snapshot["latest"] == "1.500.0"
    assert snapshot["1.400.0"] == "policyengine-simulation-py3-8-0"


def test_update_version_dict__advances_latest_when_incoming_newer(patched_modal):
    stores = patched_modal
    stores["main/simulation-api-us-versions"] = FakeDict(
        {
            "latest": "1.500.0",
            "1.500.0": "policyengine-simulation-py4-10-0",
        }
    )

    registry.update_version_dict(
        "simulation-api-us-versions",
        "main",
        "1.601.2",
        "policyengine-simulation-py4-11-0",
    )

    snapshot = stores["main/simulation-api-us-versions"].snapshot()
    assert snapshot["latest"] == "1.601.2"


def test_update_version_dict__force_latest_allows_downgrade(patched_modal):
    stores = patched_modal
    stores["main/simulation-api-us-versions"] = FakeDict(
        {
            "latest": "1.500.0",
            "1.500.0": "policyengine-simulation-py4-10-0",
        }
    )

    registry.update_version_dict(
        "simulation-api-us-versions",
        "main",
        "1.400.0",
        "policyengine-simulation-py3-8-0",
        force_latest=True,
    )

    snapshot = stores["main/simulation-api-us-versions"].snapshot()
    assert snapshot["latest"] == "1.400.0"


def test_update_version_dict__new_registry_sets_latest_even_without_force(
    patched_modal,
):
    registry.update_version_dict(
        "simulation-api-uk-versions",
        "staging",
        "2.66.0",
        "policyengine-simulation-py4-10-0",
    )

    snapshot = patched_modal["staging/simulation-api-uk-versions"].snapshot()
    assert snapshot["latest"] == "2.66.0"
    assert snapshot["2.66.0"] == "policyengine-simulation-py4-10-0"


def test_main_updates_policyengine_and_country_registries(
    patched_modal,
    monkeypatch,
):
    def fake_country_bundle_metadata(
        country: str,
    ) -> registry.CountryBundleMetadata:
        return {
            "country": country,
            "model_package_name": (
                "policyengine-us" if country == "us" else "policyengine-uk"
            ),
            "model_version": "1.687.0" if country == "us" else "2.88.14",
            "data_package_name": (
                "policyengine-us-data" if country == "us" else "policyengine-uk-data"
            ),
            "data_version": "1.78.2" if country == "us" else "1.55.5",
            "data_artifact_revision": "1.78.2" if country == "us" else "1.55.5",
            "default_dataset": (
                "enhanced_cps_2024" if country == "us" else "enhanced_frs_2023_24"
            ),
            "default_dataset_uri": f"hf://datasets/policyengine/{country}/default",
            "dataset_uris": {"default": f"hf://datasets/policyengine/{country}"},
            "dataset_aliases": {},
        }

    monkeypatch.setattr(
        registry, "_country_bundle_metadata", fake_country_bundle_metadata
    )
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

    py_versions = patched_modal["main/simulation-api-policyengine-versions"].snapshot()
    assert py_versions["latest"] == "4.19.1"
    assert py_versions["4.19.1"] == "policyengine-simulation-py4-19-1"
    assert (
        patched_modal["main/simulation-api-us-versions"].snapshot()["1.687.0"]
        == "policyengine-simulation-py4-19-1"
    )
    app_release_bundles = patched_modal[
        "main/simulation-api-app-release-bundles"
    ].snapshot()
    assert app_release_bundles["4.19.1"]["policyengine_version"] == "4.19.1"


def test_put_app_release_bundle_metadata_records_app_and_py_version_aliases(
    patched_modal,
    monkeypatch,
):
    def fake_country_bundle_metadata(
        country: str,
    ) -> registry.CountryBundleMetadata:
        return {
            "country": country,
            "model_package_name": (
                "policyengine-us" if country == "us" else "policyengine-uk"
            ),
            "model_version": "1.0.0" if country == "us" else "2.0.0",
            "data_package_name": (
                "policyengine-us-data" if country == "us" else "policyengine-uk-data"
            ),
            "data_version": "3.0.0" if country == "us" else "4.0.0",
            "data_artifact_revision": "sha-us" if country == "us" else "sha-uk",
            "default_dataset": "default",
            "default_dataset_uri": f"hf://datasets/policyengine/{country}/default",
            "dataset_uris": {"default": f"hf://datasets/policyengine/{country}"},
            "dataset_aliases": {"alias": "default"},
        }

    monkeypatch.setattr(
        registry, "_country_bundle_metadata", fake_country_bundle_metadata
    )

    registry.put_app_release_bundle_metadata(
        environment="main",
        app_name="policyengine-simulation-py4-10-0",
        policyengine_version="4.10.0",
    )

    snapshot = patched_modal["main/simulation-api-app-release-bundles"].snapshot()
    metadata = snapshot["policyengine-simulation-py4-10-0"]
    assert snapshot["4.10.0"] == metadata
    assert metadata["policyengine_version"] == "4.10.0"
    assert metadata["us"]["dataset_aliases"] == {"alias": "default"}


def test_backfill_app_release_bundle_metadata_adds_artifact_revision_from_uri():
    metadata = {
        "app_name": "policyengine-simulation-py4-13-1",
        "policyengine_version": "4.13.1",
        "us": {
            "data_version": "1.115.5",
            "default_dataset": "enhanced_cps_2024",
            "default_dataset_uri": (
                "hf://policyengine/policyengine-us-data/"
                "enhanced_cps_2024.h5@d47fb5475144260a75467d2f2e22b2d5d53d4d57"
            ),
            "dataset_uris": {},
        },
        "uk": {
            "data_version": "1.55.10",
            "default_dataset": "enhanced_frs_2023_24",
            "default_dataset_uri": (
                "hf://policyengine/policyengine-uk-data-private/"
                "enhanced_frs_2023_24.h5@655dd07e4bb9c777b00dac044949611f1feb824f"
            ),
            "dataset_uris": {},
        },
    }

    updated, changed = registry.backfill_app_release_bundle_metadata(metadata)

    assert changed is True
    assert updated is not None
    assert (
        updated["us"]["data_artifact_revision"]
        == "d47fb5475144260a75467d2f2e22b2d5d53d4d57"
    )
    assert (
        updated["uk"]["data_artifact_revision"]
        == "655dd07e4bb9c777b00dac044949611f1feb824f"
    )
    assert "data_artifact_revision" not in metadata["us"]


def test_backfill_app_release_bundle_metadata_preserves_existing_revision():
    metadata = {
        "app_name": "policyengine-simulation-py4-10-0",
        "policyengine_version": "4.10.0",
        "us": {
            "data_version": "1.110.12",
            "data_artifact_revision": "existing-us-revision",
            "default_dataset": "enhanced_cps_2024",
            "default_dataset_uri": (
                "hf://policyengine/policyengine-us-data/"
                "enhanced_cps_2024.h5@new-us-revision"
            ),
            "dataset_uris": {},
        },
        "uk": {
            "data_version": "1.40.3",
            "data_artifact_revision": "existing-uk-revision",
            "default_dataset": "enhanced_frs_2023_24",
            "default_dataset_uri": (
                "hf://policyengine/policyengine-uk-data-private/"
                "enhanced_frs_2023_24.h5@new-uk-revision"
            ),
            "dataset_uris": {},
        },
    }

    updated, changed = registry.backfill_app_release_bundle_metadata(metadata)

    assert changed is False
    assert updated == metadata
    assert updated["us"]["data_artifact_revision"] == "existing-us-revision"
    assert updated["uk"]["data_artifact_revision"] == "existing-uk-revision"


def test_backfill_app_release_bundles_updates_all_alias_entries(patched_modal):
    legacy_bundle = {
        "app_name": "policyengine-simulation-py4-13-1",
        "policyengine_version": "4.13.1",
        "us": {
            "data_version": "1.115.5",
            "default_dataset": "enhanced_cps_2024",
            "default_dataset_uri": (
                "hf://policyengine/policyengine-us-data/"
                "enhanced_cps_2024.h5@d47fb5475144260a75467d2f2e22b2d5d53d4d57"
            ),
            "dataset_uris": {},
        },
        "uk": {
            "data_version": "1.55.10",
            "default_dataset": "enhanced_frs_2023_24",
            "default_dataset_uri": (
                "hf://policyengine/policyengine-uk-data-private/"
                "enhanced_frs_2023_24.h5@655dd07e4bb9c777b00dac044949611f1feb824f"
            ),
            "dataset_uris": {},
        },
    }
    patched_modal["main/simulation-api-app-release-bundles"] = FakeDict(
        {
            "policyengine-simulation-py4-13-1": deepcopy(legacy_bundle),
            "4.13.1": deepcopy(legacy_bundle),
            "policyengine-simulation-py4-10-0": {
                "us": {"data_artifact_revision": "already-present"},
            },
        }
    )

    updated_count = registry.backfill_app_release_bundles(environment="main")

    assert updated_count == 2
    snapshot = patched_modal["main/simulation-api-app-release-bundles"].snapshot()
    for key in ("policyengine-simulation-py4-13-1", "4.13.1"):
        assert (
            snapshot[key]["uk"]["data_artifact_revision"]
            == "655dd07e4bb9c777b00dac044949611f1feb824f"
        )
    assert snapshot["policyengine-simulation-py4-10-0"] == {
        "us": {"data_artifact_revision": "already-present"},
    }
