"""Helpers for using policyengine.py bundle metadata.

The simulation API deploys separate versioned worker apps. The package and data
artifact versions come from the policyengine.py bundle manifest, and worker
images may also include the certified dataset files installed from that bundle.
"""

from __future__ import annotations

import json
import os
from collections.abc import Mapping
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from policyengine_api_simulation.dataset_uri import (
    runtime_dataset_uri,
    select_dataset_revision,
    split_dataset_revision,
)
from policyengine_api_simulation.hf_dataset import with_hf_revision

os.environ.setdefault("POLICYENGINE_SKIP_COUNTRY_IMPORTS", "1")

SUPPORTED_COUNTRIES = frozenset({"us", "uk"})
BUNDLE_RECEIPT_FILENAME = ".policyengine-bundle.json"

DATASET_ALIASES: dict[str, dict[str, str]] = {
    "us": {
        "enhanced_cps": "enhanced_cps_2024",
        "enhanced_cps_2024": "enhanced_cps_2024",
        "cps_small": "cps_small_2024",
        "cps_small_2024": "cps_small_2024",
        "cps": "hf://policyengine/policyengine-us-data/cps_2023.h5@1.110.12",
        "cps_2023": "hf://policyengine/policyengine-us-data/cps_2023.h5@1.110.12",
        "pooled_cps": "hf://policyengine/policyengine-us-data/pooled_3_year_cps_2023.h5@1.110.12",
        "pooled_3_year_cps_2023": "hf://policyengine/policyengine-us-data/pooled_3_year_cps_2023.h5@1.110.12",
    },
    "uk": {
        "enhanced_frs": "enhanced_frs_2023_24",
        "enhanced_frs_2023_24": "enhanced_frs_2023_24",
        "frs": "frs_2023_24",
        "frs_2023_24": "frs_2023_24",
    },
}


@dataclass(frozen=True)
class CountryReleaseBundle:
    country: str
    policyengine_version: str
    model_package_name: str
    model_version: str
    data_package_name: str
    data_version: str
    data_artifact_revision: str
    default_dataset: str
    default_dataset_uri: str
    dataset_uris: Mapping[str, str]


def _normalise_country(country: str) -> str:
    country = country.lower()
    if country not in SUPPORTED_COUNTRIES:
        raise ValueError(f"Unsupported country: {country}")
    return country


def _artifact_revision(data_package) -> str:
    return data_package.release_manifest_revision or data_package.version


def _current_policyengine_bundle() -> Mapping | None:
    try:
        from policyengine.bundle import get_current_bundle

        return get_current_bundle()
    except Exception:
        try:
            from policyengine.stack import get_current_stack

            return get_current_stack()
        except Exception:
            return None


def _bundle_country_metadata(
    country: str,
) -> tuple[Mapping, Mapping, Mapping, Mapping] | None:
    bundle = _current_policyengine_bundle()
    if not isinstance(bundle, Mapping):
        return None
    country_metadata = bundle.get("countries", {}).get(country)
    if not isinstance(country_metadata, Mapping):
        return None
    packages = bundle.get("packages", {})
    model_package = packages.get(country_metadata.get("model_package"))
    data_package = packages.get(country_metadata.get("data_package"), {})
    data_releases = bundle.get("data_releases", {})
    data_release = (
        data_releases.get(country, {}) if isinstance(data_releases, Mapping) else {}
    )
    if not isinstance(model_package, Mapping):
        return None
    if not isinstance(data_package, Mapping):
        data_package = {}
    if not isinstance(data_release, Mapping):
        data_release = {}
    return bundle, model_package, data_package, data_release


@lru_cache
def get_country_release_bundle(country: str) -> CountryReleaseBundle:
    """Return package and dataset versions from policyengine.py metadata."""

    country = _normalise_country(country)
    from policyengine.provenance.manifest import build_hf_uri, get_release_manifest

    manifest = get_release_manifest(country)
    bundle_metadata = _bundle_country_metadata(country)
    policyengine_version = manifest.policyengine_version
    model_package_name = manifest.model_package.name
    model_version = manifest.model_package.version
    data_package_name = manifest.data_package.name
    data_version = manifest.data_package.version
    data_artifact_revision = _artifact_revision(manifest.data_package)
    default_dataset = manifest.default_dataset
    default_dataset_uri = manifest.default_dataset_uri
    if bundle_metadata is not None:
        bundle_manifest, model_package, data_package, data_release = bundle_metadata
        policyengine_version = (
            bundle_manifest.get("policyengine_version") or policyengine_version
        )
        model_package_name = model_package.get("name") or model_package_name
        model_version = model_package.get("version") or model_version
        data_package_name = (
            data_release.get("data_package")
            or data_package.get("name")
            or data_package_name
        )
        data_version = (
            data_release.get("version") or data_package.get("version") or data_version
        )
        data_artifact_revision = data_release.get("artifact_revision") or data_version
        default_dataset = data_release.get("default_dataset") or default_dataset
        default_dataset_uri = (
            data_release.get("default_dataset_uri") or default_dataset_uri
        )
    dataset_uris = {
        name: build_hf_uri(
            repo_id=manifest.data_package.repo_id,
            path_in_repo=reference.path,
            revision=reference.revision or _artifact_revision(manifest.data_package),
        )
        for name, reference in manifest.datasets.items()
    }
    if default_dataset and default_dataset_uri:
        dataset_uris.setdefault(default_dataset, default_dataset_uri)

    return CountryReleaseBundle(
        country=country,
        policyengine_version=str(policyengine_version),
        model_package_name=str(model_package_name),
        model_version=str(model_version),
        data_package_name=str(data_package_name),
        data_version=str(data_version),
        data_artifact_revision=str(data_artifact_revision),
        default_dataset=str(default_dataset),
        default_dataset_uri=str(default_dataset_uri),
        dataset_uris=dataset_uris,
    )


def get_bundled_country_model_version(country: str) -> str:
    return get_country_release_bundle(country).model_version


def _split_requested_revision(requested_data: str) -> tuple[str, str | None]:
    if "@" not in requested_data:
        return requested_data, None
    dataset_name, revision = requested_data.rsplit("@", maxsplit=1)
    if not dataset_name or not revision:
        raise ValueError(f"Invalid dataset revision reference: {requested_data}")
    return dataset_name, revision


def resolve_bundle_dataset_name(country: str, requested_data: str | None) -> str:
    bundle = get_country_release_bundle(country)
    if requested_data is None:
        return bundle.default_dataset

    if "://" in requested_data:
        return requested_data

    requested_without_revision, revision = _split_requested_revision(requested_data)
    aliased = DATASET_ALIASES.get(bundle.country, {}).get(
        requested_without_revision, requested_data
    )
    if revision is not None:
        if "://" in aliased:
            return with_hf_revision(aliased, revision)
        uri = bundle.dataset_uris.get(aliased)
        if uri is None:
            raise ValueError(
                "Unknown dataset revision reference "
                f"{requested_data!r} for country {bundle.country!r}"
            )
        return with_hf_revision(uri, revision)
    return aliased


def resolve_bundle_dataset_uri(country: str, requested_data: str | None) -> str:
    bundle = get_country_release_bundle(country)
    dataset_name = resolve_bundle_dataset_name(country, requested_data)
    if "://" in dataset_name:
        return dataset_name
    return bundle.dataset_uris.get(dataset_name, dataset_name)


def _receipt_path() -> Path:
    explicit = os.environ.get("POLICYENGINE_BUNDLE_RECEIPT")
    if explicit:
        return Path(explicit)
    data_folder = os.environ.get("POLICYENGINE_DATA_FOLDER", "/tmp/policyengine-data")
    return Path(data_folder) / BUNDLE_RECEIPT_FILENAME


def get_installed_bundle_receipt() -> Mapping | None:
    path = _receipt_path()
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, Mapping) else None


def _receipt_dataset(country: str) -> Mapping | None:
    receipt = get_installed_bundle_receipt()
    if not isinstance(receipt, Mapping):
        return None
    for dataset in receipt.get("datasets", []):
        if isinstance(dataset, Mapping) and dataset.get("country") == country:
            return dataset
    return None


def _is_default_bundle_dataset(
    country: str,
    requested_data: str | None,
    requested_data_version: str | None,
) -> bool:
    bundle = get_country_release_bundle(country)
    if requested_data is None:
        return requested_data_version in {None, bundle.data_version}
    if "://" in requested_data:
        return False
    requested_without_revision, requested_revision = split_dataset_revision(
        requested_data
    )
    revision = select_dataset_revision(
        requested_revision=requested_revision,
        requested_data_version=requested_data_version,
    )
    aliased = DATASET_ALIASES.get(bundle.country, {}).get(
        requested_without_revision,
        requested_without_revision,
    )
    return aliased == bundle.default_dataset and revision in {None, bundle.data_version}


def resolve_local_bundle_dataset_path(
    country: str,
    requested_data: str | None,
    requested_data_version: str | None = None,
) -> str | None:
    """Return a local certified dataset path when the request uses the default."""

    country = _normalise_country(country)
    if not _is_default_bundle_dataset(country, requested_data, requested_data_version):
        return None
    bundle = get_country_release_bundle(country)
    dataset = _receipt_dataset(country)
    if not isinstance(dataset, Mapping):
        return None
    if dataset.get("version") != bundle.data_version:
        return None
    path = dataset.get("path")
    if not isinstance(path, str):
        return None
    if not Path(path).exists():
        return None
    return path


def resolve_runtime_bundle_dataset_uri(
    country: str,
    requested_data: str | None,
    requested_data_version: str | None = None,
) -> str:
    """Resolve a request dataset to the reference the worker should load."""

    local_path = resolve_local_bundle_dataset_path(
        country,
        requested_data,
        requested_data_version,
    )
    if local_path is not None:
        return local_path

    bundle = get_country_release_bundle(country)
    if requested_data is None:
        return runtime_dataset_uri(
            bundle.default_dataset_uri,
            default_revision=bundle.data_version,
            override_revision=requested_data_version,
            artifact_revision=bundle.data_artifact_revision,
        )

    requested_without_revision, requested_revision = split_dataset_revision(
        requested_data
    )
    revision = select_dataset_revision(
        requested_revision=requested_revision,
        requested_data_version=requested_data_version,
    )

    if "://" in requested_without_revision:
        override_revision = revision if requested_data_version is not None else None
        runtime_input = (
            requested_data
            if requested_revision is not None and requested_data_version is None
            else requested_without_revision
        )
        return runtime_dataset_uri(
            runtime_input,
            default_revision=(
                bundle.data_version
                if requested_without_revision.startswith("hf://")
                else None
            ),
            override_revision=override_revision,
            artifact_revision=bundle.data_artifact_revision,
        )

    dataset_uri = resolve_bundle_dataset_uri(country, requested_without_revision)
    if dataset_uri == requested_without_revision:
        if revision is not None:
            raise ValueError(
                "Unknown dataset revision reference "
                f"{requested_data!r} for country {bundle.country!r}"
            )
        return requested_data

    return runtime_dataset_uri(
        dataset_uri,
        default_revision=bundle.data_version,
        override_revision=revision,
        artifact_revision=bundle.data_artifact_revision,
    )
