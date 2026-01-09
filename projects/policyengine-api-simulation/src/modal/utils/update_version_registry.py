"""
Update Modal version registries after deployment.

Usage:
    uv run python -m src.modal.utils.update_version_registry \
        --app-name policyengine-sim-v42 \
        --us-version 1.370.2 \
        --uk-version 2.22.8
"""

import argparse
import modal


def main():
    parser = argparse.ArgumentParser(description="Update version registries")
    parser.add_argument("--app-name", required=True, help="App name (e.g., policyengine-sim-v42)")
    parser.add_argument("--us-version", required=True, help="US package version")
    parser.add_argument("--uk-version", required=True, help="UK package version")
    args = parser.parse_args()

    # Update US registry
    us_dict = modal.Dict.from_name("simulation-api-us-versions", create_if_missing=True)
    us_dict[args.us_version] = args.app_name
    us_dict["latest"] = args.us_version
    print(f"Updated simulation-api-us-versions: {args.us_version} -> {args.app_name}")
    print(f"Updated simulation-api-us-versions: latest -> {args.us_version}")

    # Update UK registry
    uk_dict = modal.Dict.from_name("simulation-api-uk-versions", create_if_missing=True)
    uk_dict[args.uk_version] = args.app_name
    uk_dict["latest"] = args.uk_version
    print(f"Updated simulation-api-uk-versions: {args.uk_version} -> {args.app_name}")
    print(f"Updated simulation-api-uk-versions: latest -> {args.uk_version}")


if __name__ == "__main__":
    main()
