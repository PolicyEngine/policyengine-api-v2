#!/bin/bash
# Extract policyengine-us and policyengine-uk versions from uv.lock
# Usage: ./modal-extract-versions.sh <project-dir>
# Outputs: Sets us_version and uk_version in GITHUB_OUTPUT

set -euo pipefail

PROJECT_DIR="${1:-.}"

cd "$PROJECT_DIR"

US_VERSION=$(grep -A1 'name = "policyengine-us"' uv.lock | grep version | head -1 | sed 's/.*"\(.*\)".*/\1/')
UK_VERSION=$(grep -A1 'name = "policyengine-uk"' uv.lock | grep version | head -1 | sed 's/.*"\(.*\)".*/\1/')

echo "us_version=$US_VERSION" >> "$GITHUB_OUTPUT"
echo "uk_version=$UK_VERSION" >> "$GITHUB_OUTPUT"
echo "Deploying with policyengine-us=$US_VERSION, policyengine-uk=$UK_VERSION"
