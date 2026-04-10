from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Callable, Mapping

from policyengine_fastapi.observability import (
    LaunchedVersionRecord,
    VersionCatalogSnapshot,
)


CountryCode = str
RegistryLoader = Callable[[str, str | None], Mapping[str, str]]
COUNTRIES: tuple[CountryCode, ...] = ("us", "uk")


def get_registry_name(country: str) -> str:
    normalized = country.lower()
    if normalized not in COUNTRIES:
        raise ValueError(f"Unknown country: {country}")
    return f"simulation-api-{normalized}-versions"


def _version_sort_key(version: str) -> tuple[tuple[int, int | str], ...]:
    parts: list[tuple[int, int | str]] = []
    for raw_part in version.replace("-", ".").split("."):
        if raw_part.isdigit():
            parts.append((0, int(raw_part)))
        else:
            parts.append((1, raw_part))
    return tuple(parts)


def normalize_version_registry(
    *,
    country: str,
    registry: Mapping[str, str],
    environment: str | None = None,
    fetched_at: datetime | None = None,
) -> VersionCatalogSnapshot:
    registry_name = get_registry_name(country)
    latest_version = registry.get("latest")
    version_records = [
        LaunchedVersionRecord(
            country=country.lower(),
            country_package_version=version,
            modal_app_name=app_name,
            registry_name=registry_name,
            is_latest=version == latest_version,
            is_active=bool(app_name),
        )
        for version, app_name in registry.items()
        if version != "latest"
    ]
    version_records.sort(
        key=lambda item: _version_sort_key(item.country_package_version),
        reverse=True,
    )
    return VersionCatalogSnapshot(
        country=country.lower(),
        registry_name=registry_name,
        environment=environment,
        latest_version=latest_version,
        fetched_at=fetched_at or datetime.now(UTC),
        versions=version_records,
    )


def coerce_registry_mapping(registry: Mapping[str, str] | object) -> dict[str, str]:
    if isinstance(registry, dict):
        return dict(registry)
    if hasattr(registry, "items"):
        return dict(getattr(registry, "items")())
    return dict(registry)


@dataclass
class CachedVersionCatalogSnapshot:
    snapshot: VersionCatalogSnapshot
    expires_at: datetime


class VersionCatalogService:
    def __init__(
        self,
        *,
        loader: RegistryLoader,
        environment: str | None = None,
        cache_ttl: timedelta = timedelta(minutes=5),
        clock: Callable[[], datetime] | None = None,
    ):
        self.loader = loader
        self.environment = environment
        self.cache_ttl = cache_ttl
        self.clock = clock or (lambda: datetime.now(UTC))
        self._cache: dict[str, CachedVersionCatalogSnapshot] = {}

    def get_country_snapshot(
        self,
        country: str,
        *,
        refresh: bool = False,
    ) -> VersionCatalogSnapshot:
        normalized = country.lower()
        if normalized not in COUNTRIES:
            raise ValueError(f"Unknown country: {country}")

        cached = self._cache.get(normalized)
        now = self.clock()
        if not refresh and cached is not None and cached.expires_at >= now:
            return cached.snapshot

        registry_name = get_registry_name(normalized)
        try:
            registry = coerce_registry_mapping(
                self.loader(registry_name, self.environment)
            )
        except Exception:
            if cached is not None:
                return cached.snapshot
            raise

        snapshot = normalize_version_registry(
            country=normalized,
            registry=registry,
            environment=self.environment,
            fetched_at=now,
        )
        self._cache[normalized] = CachedVersionCatalogSnapshot(
            snapshot=snapshot,
            expires_at=now + self.cache_ttl,
        )
        return snapshot

    def get_all_snapshots(
        self,
        *,
        refresh: bool = False,
    ) -> dict[str, VersionCatalogSnapshot]:
        return {
            country: self.get_country_snapshot(country, refresh=refresh)
            for country in COUNTRIES
        }

    def get_country_registry(
        self,
        country: str,
        *,
        refresh: bool = False,
    ) -> dict[str, str]:
        snapshot = self.get_country_snapshot(country, refresh=refresh)
        registry = {
            record.country_package_version: record.modal_app_name
            for record in snapshot.versions
        }
        if snapshot.latest_version is not None:
            registry["latest"] = snapshot.latest_version
        return registry

    def get_all_registries(
        self,
        *,
        refresh: bool = False,
    ) -> dict[str, dict[str, str]]:
        return {
            country: self.get_country_registry(country, refresh=refresh)
            for country in COUNTRIES
        }

    def reset_cache(self) -> None:
        self._cache.clear()
