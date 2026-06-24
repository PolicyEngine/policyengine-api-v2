"""
Update Modal version registries after deployment.

Each deployment creates a versioned policyengine.py app (e.g.,
policyengine-simulation-py4-10-0). This script updates the version dicts to map
the policyengine.py version and the bundled country package versions to that
app name.

The dicts allow the gateway to route requests for specific versions to the correct app.
Multiple versions can coexist - old deployments remain accessible via their version numbers.

When a version is re-deployed (same package version, new app), the dict entry is updated
to point to the new app. This ensures "latest" behavior uses the most recent deployment.

Usage:
    uv run python -m src.modal.utils.update_version_registry \
        --app-name policyengine-simulation-py4-10-0 \
        --policyengine-version 4.10.0 \
        --us-version 1.459.0 \
        --uk-version 2.65.9 \
        --environment staging

    uv run python -m src.modal.utils.update_version_registry \
        --environment staging \
        --backfill-app-release-bundles
"""

import argparse
import modal
from packaging.version import InvalidVersion, Version
from typing import Any, TypedDict

from policyengine_api_simulation.dataset_uri import split_dataset_revision

POLICYENGINE_VERSION_DICT_NAME = "simulation-api-policyengine-versions"
US_VERSION_DICT_NAME = "simulation-api-us-versions"
UK_VERSION_DICT_NAME = "simulation-api-uk-versions"
APP_RELEASE_BUNDLES_DICT_NAME = "simulation-api-app-release-bundles"


class CountryBundleMetadata(TypedDict):
    country: str
    model_package_name: str
    model_version: str
    data_package_name: str
    data_version: str
    data_artifact_revision: str
    default_dataset: str
    default_dataset_uri: str
    dataset_uris: dict[str, str]
    dataset_repo_types: dict[str, str]
    dataset_aliases: dict[str, str]


class AppReleaseBundleMetadata(TypedDict):
    app_name: str
    policyengine_version: str
    us: CountryBundleMetadata
    uk: CountryBundleMetadata


def _is_newer_version(candidate: str, current: str | None) -> bool:
    """Return True when ``candidate`` should replace ``current`` as 'latest'.

    If the current pointer is missing we always advance. If either version
    string is not PEP 440 parseable we fall back to a conservative rule:
    advance only when the strings differ and the operator has explicitly
    opted in via ``--force-latest``. That decision is made by the caller;
    this helper answers the strict-greater-than question for valid versions.
    """

    if current is None:
        return True
    try:
        return Version(candidate) > Version(current)
    except InvalidVersion:
        return False


def update_version_dict(
    dict_name: str,
    environment: str,
    version: str,
    app_name: str,
    *,
    force_latest: bool = False,
) -> None:
    """
    Update a version dict entry, showing previous value if overwriting.

    The mapping ``version_dict[version] -> app_name`` is always refreshed
    so redeploying the same package version to a new app remains supported.
    The ``latest`` pointer, however, is only advanced when ``version`` is a
    strict semantic improvement over the current ``latest``. Pass
    ``--force-latest`` to override (e.g. intentional downgrades or rollbacks).

    Args:
        dict_name: Name of the Modal Dict (e.g., "simulation-api-us-versions")
        environment: Modal environment (staging or main)
        version: Package version (e.g., "1.459.0")
        app_name: App name to map this version to
        force_latest: When True, overwrite ``latest`` even if ``version`` is
            older than the existing pointer.
    """
    version_dict = modal.Dict.from_name(
        dict_name,
        environment_name=environment,
        create_if_missing=True,
    )

    # Check for existing entry
    try:
        previous_app = version_dict[version]
        if previous_app != app_name:
            print(f"  {dict_name}[{version}]: {previous_app} -> {app_name}")
        else:
            print(f"  {dict_name}[{version}]: {app_name} (unchanged)")
    except KeyError:
        print(f"  {dict_name}[{version}]: (new) -> {app_name}")

    # Update entry
    version_dict[version] = app_name

    # Update latest pointer only when the incoming version is newer or
    # --force-latest was supplied.
    previous_latest = version_dict.get("latest")
    should_advance = _is_newer_version(version, previous_latest) or force_latest

    if should_advance:
        version_dict["latest"] = version
        if previous_latest != version:
            forced = (
                " [forced]"
                if force_latest and not _is_newer_version(version, previous_latest)
                else ""
            )
            print(f"  {dict_name}[latest]: {previous_latest} -> {version}{forced}")
        else:
            print(f"  {dict_name}[latest]: {version} (unchanged)")
    else:
        print(
            f"  {dict_name}[latest]: {previous_latest} (kept; incoming "
            f"{version} is not newer, pass --force-latest to override)"
        )


def _country_bundle_metadata(country: str) -> CountryBundleMetadata:
    from policyengine_api_simulation.release_bundle import (
        DATASET_ALIASES,
        get_country_release_bundle,
    )

    bundle = get_country_release_bundle(country)
    return {
        "country": bundle.country,
        "model_package_name": bundle.model_package_name,
        "model_version": bundle.model_version,
        "data_package_name": bundle.data_package_name,
        "data_version": bundle.data_version,
        "data_artifact_revision": bundle.data_artifact_revision,
        "default_dataset": bundle.default_dataset,
        "default_dataset_uri": bundle.default_dataset_uri,
        "dataset_uris": dict(bundle.dataset_uris),
        "dataset_repo_types": dict(bundle.dataset_repo_types),
        "dataset_aliases": dict(DATASET_ALIASES.get(bundle.country, {})),
    }


def build_app_release_bundle_metadata(
    *,
    app_name: str,
    policyengine_version: str,
) -> AppReleaseBundleMetadata:
    return {
        "app_name": app_name,
        "policyengine_version": policyengine_version,
        "us": _country_bundle_metadata("us"),
        "uk": _country_bundle_metadata("uk"),
    }


def _dataset_revision(dataset_uri: object) -> str | None:
    if not isinstance(dataset_uri, str):
        return None
    try:
        _, revision = split_dataset_revision(dataset_uri)
    except ValueError:
        return None
    return revision


def _infer_data_artifact_revision(country_bundle: dict[str, Any]) -> str | None:
    candidates: list[object] = [country_bundle.get("default_dataset_uri")]
    default_dataset = country_bundle.get("default_dataset")
    dataset_uris = country_bundle.get("dataset_uris")
    if isinstance(default_dataset, str) and isinstance(dataset_uris, dict):
        candidates.append(dataset_uris.get(default_dataset))
    if isinstance(dataset_uris, dict):
        candidates.extend(dataset_uris.values())

    for candidate in candidates:
        revision = _dataset_revision(candidate)
        if revision is not None:
            return revision

    data_version = country_bundle.get("data_version")
    return data_version if isinstance(data_version, str) and data_version else None


def _backfill_country_bundle(
    country_bundle: dict[str, Any],
) -> tuple[dict[str, Any], bool]:
    existing_revision = country_bundle.get("data_artifact_revision")
    if isinstance(existing_revision, str) and existing_revision:
        return country_bundle, False

    artifact_revision = _infer_data_artifact_revision(country_bundle)
    if artifact_revision is None:
        return country_bundle, False

    updated = dict(country_bundle)
    updated["data_artifact_revision"] = artifact_revision
    return updated, True


def backfill_app_release_bundle_metadata(
    metadata: object,
) -> tuple[dict[str, Any] | None, bool]:
    if not isinstance(metadata, dict):
        return None, False

    updated_metadata = dict(metadata)
    changed = False
    for country in ("us", "uk"):
        country_bundle = metadata.get(country)
        if not isinstance(country_bundle, dict):
            continue
        updated_country_bundle, country_changed = _backfill_country_bundle(
            country_bundle
        )
        if country_changed:
            updated_metadata[country] = updated_country_bundle
            changed = True

    return updated_metadata, changed


def backfill_app_release_bundles(*, environment: str) -> int:
    bundle_store = modal.Dict.from_name(
        APP_RELEASE_BUNDLES_DICT_NAME,
        environment_name=environment,
        create_if_missing=True,
    )

    updated_count = 0
    for key, metadata in list(bundle_store.items()):
        updated_metadata, changed = backfill_app_release_bundle_metadata(metadata)
        if not changed or updated_metadata is None:
            continue
        bundle_store[key] = updated_metadata
        updated_count += 1
        print(f"  {APP_RELEASE_BUNDLES_DICT_NAME}[{key}]: backfilled")

    return updated_count


def put_app_release_bundle_metadata(
    *,
    environment: str,
    app_name: str,
    policyengine_version: str,
) -> None:
    bundle_store = modal.Dict.from_name(
        APP_RELEASE_BUNDLES_DICT_NAME,
        environment_name=environment,
        create_if_missing=True,
    )
    metadata = build_app_release_bundle_metadata(
        app_name=app_name,
        policyengine_version=policyengine_version,
    )
    bundle_store[app_name] = metadata
    bundle_store[policyengine_version] = metadata
    print(f"  {APP_RELEASE_BUNDLES_DICT_NAME}[{app_name}]: updated")


def main():
    parser = argparse.ArgumentParser(
        description="Update version registries after Modal deployment"
    )
    parser.add_argument(
        "--app-name",
        help="Versioned app name (e.g., policyengine-simulation-py4-10-0)",
    )
    parser.add_argument(
        "--policyengine-version",
        help="policyengine.py package version (e.g., 4.10.0)",
    )
    parser.add_argument(
        "--us-version",
        help="US package version (e.g., 1.459.0)",
    )
    parser.add_argument(
        "--uk-version",
        help="UK package version (e.g., 2.65.9)",
    )
    parser.add_argument(
        "--environment",
        required=True,
        help="Modal environment (staging or main)",
    )
    parser.add_argument(
        "--force-latest",
        action="store_true",
        help=(
            "Overwrite 'latest' even when the supplied version is older than "
            "the currently recorded latest (use for intentional rollbacks)."
        ),
    )
    parser.add_argument(
        "--backfill-app-release-bundles",
        action="store_true",
        help=(
            "Populate missing data_artifact_revision fields in existing app-release "
            "bundle metadata without changing version routing."
        ),
    )
    args = parser.parse_args()

    if args.backfill_app_release_bundles:
        print(
            "Backfilling app release bundle metadata in Modal environment: "
            f"{args.environment}"
        )
        updated_count = backfill_app_release_bundles(environment=args.environment)
        print(f"Backfilled {updated_count} app release bundle entries.")
        return

    required_args = {
        "--app-name": args.app_name,
        "--policyengine-version": args.policyengine_version,
        "--us-version": args.us_version,
        "--uk-version": args.uk_version,
    }
    missing_args = [name for name, value in required_args.items() if not value]
    if missing_args:
        parser.error(
            "the following arguments are required unless "
            f"--backfill-app-release-bundles is set: {', '.join(missing_args)}"
        )

    print(f"Updating version registries in Modal environment: {args.environment}")
    print(f"  App name: {args.app_name}")
    print(f"  policyengine.py version: {args.policyengine_version}")
    print(f"  US version: {args.us_version}")
    print(f"  UK version: {args.uk_version}")
    print()

    print("policyengine.py version registry:")
    update_version_dict(
        POLICYENGINE_VERSION_DICT_NAME,
        args.environment,
        args.policyengine_version,
        args.app_name,
        force_latest=args.force_latest,
    )
    print()

    # Update US registry
    print("US version registry:")
    update_version_dict(
        US_VERSION_DICT_NAME,
        args.environment,
        args.us_version,
        args.app_name,
        force_latest=args.force_latest,
    )
    print()

    # Update UK registry
    print("UK version registry:")
    update_version_dict(
        UK_VERSION_DICT_NAME,
        args.environment,
        args.uk_version,
        args.app_name,
        force_latest=args.force_latest,
    )
    print()

    print("App release bundle metadata:")
    put_app_release_bundle_metadata(
        environment=args.environment,
        app_name=args.app_name,
        policyengine_version=args.policyengine_version,
    )
    print()

    print("Version registries updated successfully.")


if __name__ == "__main__":
    main()
