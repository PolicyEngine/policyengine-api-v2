"""
Update Modal version registries after deployment.

Each deployment creates a versioned app (e.g., policyengine-simulation-us1-459-0-uk2-65-9).
This script updates the version dicts to map package versions to app names.

The dicts allow the gateway to route requests for specific versions to the correct app.
Multiple versions can coexist - old deployments remain accessible via their version numbers.

When a version is re-deployed (same package version, new app), the dict entry is updated
to point to the new app. This ensures "latest" behavior uses the most recent deployment.

Usage:
    uv run python -m src.modal.utils.update_version_registry \
        --app-name policyengine-simulation-us1-459-0-uk2-65-9 \
        --us-version 1.459.0 \
        --uk-version 2.65.9 \
        --environment staging
"""

import argparse
import modal
from packaging.version import InvalidVersion, Version


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


def main():
    parser = argparse.ArgumentParser(
        description="Update version registries after Modal deployment"
    )
    parser.add_argument(
        "--app-name",
        required=True,
        help="Versioned app name (e.g., policyengine-simulation-us1-459-0-uk2-65-9)",
    )
    parser.add_argument(
        "--us-version",
        required=True,
        help="US package version (e.g., 1.459.0)",
    )
    parser.add_argument(
        "--uk-version",
        required=True,
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
    args = parser.parse_args()

    print(f"Updating version registries in Modal environment: {args.environment}")
    print(f"  App name: {args.app_name}")
    print(f"  US version: {args.us_version}")
    print(f"  UK version: {args.uk_version}")
    print()

    # Update US registry
    print("US version registry:")
    update_version_dict(
        "simulation-api-us-versions",
        args.environment,
        args.us_version,
        args.app_name,
        force_latest=args.force_latest,
    )
    print()

    # Update UK registry
    print("UK version registry:")
    update_version_dict(
        "simulation-api-uk-versions",
        args.environment,
        args.uk_version,
        args.app_name,
        force_latest=args.force_latest,
    )
    print()

    print("Version registries updated successfully.")


if __name__ == "__main__":
    main()
