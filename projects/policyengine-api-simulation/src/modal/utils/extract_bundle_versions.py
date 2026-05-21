"""Print policyengine.py bundle versions for deployment scripts."""

from __future__ import annotations

import os
from pathlib import Path

from src.modal.release_bundle import get_country_release_bundle


def main() -> None:
    us_bundle = get_country_release_bundle("us")
    uk_bundle = get_country_release_bundle("uk")

    outputs = {
        "policyengine_version": us_bundle.policyengine_version,
        "us_version": us_bundle.model_version,
        "us_data_version": us_bundle.data_version,
        "uk_version": uk_bundle.model_version,
        "uk_data_version": uk_bundle.data_version,
    }

    github_output = os.environ.get("GITHUB_OUTPUT")
    if github_output:
        output_path = Path(github_output)
        with output_path.open("a", encoding="utf-8") as file:
            for key, value in outputs.items():
                file.write(f"{key}={value}\n")

    print(
        "Deploying with policyengine.py bundle "
        f"{outputs['policyengine_version']}: "
        f"policyengine-us={outputs['us_version']}, "
        f"policyengine-us-data={outputs['us_data_version']}, "
        f"policyengine-uk={outputs['uk_version']}, "
        f"policyengine-uk-data={outputs['uk_data_version']}"
    )


if __name__ == "__main__":
    main()
