#!/bin/bash
# Extract policyengine.py, policyengine-core, policyengine-us,
# policyengine-us-data, policyengine-uk, and policyengine-uk-data versions.
# Usage: ./modal-extract-versions.sh <project-dir>
# Outputs: Sets policyengine_version, policyengine_core_version, us_version,
# us_data_version, uk_version, and uk_data_version in GITHUB_OUTPUT

set -euo pipefail

PROJECT_DIR="${1:-.}"

cd "$PROJECT_DIR"

uv run python -m src.modal.utils.extract_bundle_versions
