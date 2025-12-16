#!/bin/bash
#
# Updates the deployments.json manifest in GCS after a successful deployment.
#
# Usage:
#   ./scripts/update-deployments-manifest.sh <bucket> <revision> <us_version> <uk_version>
#
# Arguments:
#   bucket      - GCS bucket name (e.g., "my-project-metadata")
#   revision    - Full revision path from Terraform output
#   us_version  - US package version (e.g., "1.2.3")
#   uk_version  - UK package version (e.g., "2.0.0")
#
# The script performs an atomic update by:
# 1. Downloading the existing manifest (or creating empty array)
# 2. Appending the new deployment entry
# 3. Writing to a temp file, then copying to final location
#

set -euo pipefail

BUCKET="$1"
REVISION="$2"
US_VERSION="$3"
UK_VERSION="$4"

DEPLOYED_AT=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
TEMP_FILE=$(mktemp)
TEMP_FILE_UPDATED=$(mktemp)

cleanup() {
    rm -f "$TEMP_FILE" "$TEMP_FILE_UPDATED"
}
trap cleanup EXIT

echo "Updating deployments manifest in gs://${BUCKET}/deployments.json"

# Download existing manifest or create empty array
if gcloud storage cat "gs://${BUCKET}/deployments.json" > "$TEMP_FILE" 2>/dev/null; then
    echo "Found existing deployments manifest"
else
    echo "[]" > "$TEMP_FILE"
    echo "Created new deployments manifest"
fi

# Create new deployment entry
NEW_ENTRY=$(jq -n \
    --arg revision "$REVISION" \
    --arg us "$US_VERSION" \
    --arg uk "$UK_VERSION" \
    --arg deployed_at "$DEPLOYED_AT" \
    '{revision: $revision, us: $us, uk: $uk, deployed_at: $deployed_at}')

echo "Adding deployment entry:"
echo "$NEW_ENTRY" | jq .

# Append to manifest
jq ". + [$NEW_ENTRY]" "$TEMP_FILE" > "$TEMP_FILE_UPDATED"

# Upload to GCS (gcloud storage cp is atomic for single files)
gcloud storage cp "$TEMP_FILE_UPDATED" "gs://${BUCKET}/deployments.json"

echo "Successfully updated deployments manifest"
echo "  Revision: $REVISION"
echo "  US Version: $US_VERSION"
echo "  UK Version: $UK_VERSION"
echo "  Deployed At: $DEPLOYED_AT"
