#!/bin/bash
# Deploy simulation API to Modal
# Usage: ./modal-deploy-app.sh <modal-environment> <app-file>
# Required env vars: POLICYENGINE_US_VERSION, POLICYENGINE_UK_VERSION

set -euo pipefail

MODAL_ENV="${1:?Modal environment required}"
APP_FILE="${2:-src/modal/app.py}"

echo "Deploying to Modal environment: $MODAL_ENV"
echo "  US version: ${POLICYENGINE_US_VERSION:-not set}"
echo "  UK version: ${POLICYENGINE_UK_VERSION:-not set}"

uv run modal deploy --env="$MODAL_ENV" "$APP_FILE"

echo "Deployment complete"
