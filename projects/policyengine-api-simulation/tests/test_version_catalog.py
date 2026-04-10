from datetime import UTC, datetime, timedelta

import pytest
from policyengine_fastapi.observability import VersionCatalogSnapshot

from policyengine_api_simulation.version_catalog import (
    coerce_registry_mapping,
    VersionCatalogService,
    get_registry_name,
    normalize_version_registry,
)


def test_normalize_version_registry__sorts_versions_and_marks_latest():
    snapshot = normalize_version_registry(
        country="us",
        registry={
            "latest": "1.632.5",
            "1.606.1": "policyengine-simulation-us1-606-1-uk2-75-2",
            "1.632.5": "policyengine-simulation-us1-632-5-uk2-78-0",
            "1.500.0": "policyengine-simulation-us1-500-0-uk2-66-0",
        },
        environment="main",
        fetched_at=datetime(2026, 4, 10, 12, 0, tzinfo=UTC),
    )

    assert snapshot == VersionCatalogSnapshot(
        country="us",
        registry_name="simulation-api-us-versions",
        environment="main",
        latest_version="1.632.5",
        fetched_at=datetime(2026, 4, 10, 12, 0, tzinfo=UTC),
        versions=[
            {
                "country": "us",
                "country_package_version": "1.632.5",
                "modal_app_name": "policyengine-simulation-us1-632-5-uk2-78-0",
                "registry_name": "simulation-api-us-versions",
                "is_latest": True,
                "is_active": True,
            },
            {
                "country": "us",
                "country_package_version": "1.606.1",
                "modal_app_name": "policyengine-simulation-us1-606-1-uk2-75-2",
                "registry_name": "simulation-api-us-versions",
                "is_latest": False,
                "is_active": True,
            },
            {
                "country": "us",
                "country_package_version": "1.500.0",
                "modal_app_name": "policyengine-simulation-us1-500-0-uk2-66-0",
                "registry_name": "simulation-api-us-versions",
                "is_latest": False,
                "is_active": True,
            },
        ],
    )


def test_version_catalog_service__returns_cached_snapshot_on_loader_failure():
    registries = {
        "simulation-api-us-versions": {
            "latest": "1.632.5",
            "1.632.5": "policyengine-simulation-us1-632-5-uk2-78-0",
        }
    }
    calls = []
    clock_ticks = iter(
        (
            datetime(2026, 4, 10, 12, 0, tzinfo=UTC),
            datetime(2026, 4, 10, 12, 1, tzinfo=UTC),
        )
    )

    def loader(dict_name: str, environment: str | None):
        calls.append((dict_name, environment))
        if len(calls) > 1:
            raise RuntimeError("modal unavailable")
        return registries[dict_name]

    service = VersionCatalogService(
        loader=loader,
        environment="main",
        cache_ttl=timedelta(seconds=0),
        clock=lambda: next(clock_ticks),
    )

    first = service.get_country_snapshot("us")
    second = service.get_country_snapshot("us")

    assert len(calls) == 2
    assert second == first


def test_version_catalog_service__returns_all_countries_and_preserves_empty_registry():
    registries = {
        "simulation-api-us-versions": {
            "latest": "1.632.5",
            "1.632.5": "policyengine-simulation-us1-632-5-uk2-78-0",
        },
        "simulation-api-uk-versions": {},
    }
    service = VersionCatalogService(
        loader=lambda dict_name, environment: registries[dict_name],
        environment="staging",
    )

    snapshots = service.get_all_snapshots()

    assert set(snapshots) == {"us", "uk"}
    assert snapshots["us"].latest_version == "1.632.5"
    assert snapshots["uk"].versions == []
    assert snapshots["uk"].latest_version is None


def test_get_registry_name__rejects_unknown_country():
    with pytest.raises(ValueError, match="Unknown country"):
        get_registry_name("ca")


def test_coerce_registry_mapping__supports_item_providers():
    class FakeRegistry:
        def items(self):
            return {"latest": "1.632.5", "1.632.5": "app"}.items()

    assert coerce_registry_mapping(FakeRegistry()) == {
        "latest": "1.632.5",
        "1.632.5": "app",
    }
