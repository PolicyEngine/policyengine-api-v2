"""Tests for the Modal version-registry updater."""

from __future__ import annotations

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
            "1.500.0": "policyengine-simulation-us1-500-0-uk2-66-0",
        }
    )

    registry.update_version_dict(
        "simulation-api-us-versions",
        "main",
        "1.400.0",
        "policyengine-simulation-us1-400-0-uk2-66-0",
    )

    snapshot = stores["main/simulation-api-us-versions"].snapshot()
    assert snapshot["latest"] == "1.500.0"
    assert snapshot["1.400.0"] == "policyengine-simulation-us1-400-0-uk2-66-0"


def test_update_version_dict__advances_latest_when_incoming_newer(patched_modal):
    stores = patched_modal
    stores["main/simulation-api-us-versions"] = FakeDict(
        {
            "latest": "1.500.0",
            "1.500.0": "policyengine-simulation-us1-500-0-uk2-66-0",
        }
    )

    registry.update_version_dict(
        "simulation-api-us-versions",
        "main",
        "1.601.2",
        "policyengine-simulation-us1-601-2-uk2-70-0",
    )

    snapshot = stores["main/simulation-api-us-versions"].snapshot()
    assert snapshot["latest"] == "1.601.2"


def test_update_version_dict__force_latest_allows_downgrade(patched_modal):
    stores = patched_modal
    stores["main/simulation-api-us-versions"] = FakeDict(
        {
            "latest": "1.500.0",
            "1.500.0": "policyengine-simulation-us1-500-0-uk2-66-0",
        }
    )

    registry.update_version_dict(
        "simulation-api-us-versions",
        "main",
        "1.400.0",
        "policyengine-simulation-us1-400-0-uk2-66-0",
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
        "policyengine-simulation-us1-500-0-uk2-66-0",
    )

    snapshot = patched_modal["staging/simulation-api-uk-versions"].snapshot()
    assert snapshot["latest"] == "2.66.0"
    assert snapshot["2.66.0"] == "policyengine-simulation-us1-500-0-uk2-66-0"
