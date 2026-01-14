#!/bin/bash
# Deploy simulation API to Modal
# Usage: ./modal-deploy-app.sh <modal-environment> <app-file>
# Required env vars: POLICYENGINE_US_VERSION, POLICYENGINE_UK_VERSION

set -euo pipefail

MODAL_ENV="${1:?Modal environment required}"
APP_FILE="${2:-src/modal/app.py}"

# Generate versioned app name (dots replaced with dashes for URL safety)
US_VERSION_SAFE="${POLICYENGINE_US_VERSION//./-}"
UK_VERSION_SAFE="${POLICYENGINE_UK_VERSION//./-}"
APP_NAME="policyengine-simulation-us${US_VERSION_SAFE}-uk${UK_VERSION_SAFE}"

echo "Deploying to Modal environment: $MODAL_ENV"
echo "  US version: ${POLICYENGINE_US_VERSION}"
echo "  UK version: ${POLICYENGINE_UK_VERSION}"
echo "  App name: ${APP_NAME}"

# Export app name for Modal to use
export MODAL_APP_NAME="$APP_NAME"

uv run modal deploy --env="$MODAL_ENV" "$APP_FILE"

echo "Updating version registries..."
uv run python -m src.modal.utils.update_version_registry \
    --app-name "$APP_NAME" \
    --us-version "${POLICYENGINE_US_VERSION}" \
    --uk-version "${POLICYENGINE_UK_VERSION}" \
    --environment "$MODAL_ENV"

echo "Deployment complete"
echo "  App deployed: $APP_NAME"
