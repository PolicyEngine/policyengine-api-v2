#!/bin/bash
# Deploy simulation API to Modal
# Usage: ./modal-deploy-app.sh <modal-environment>
# Required env vars: POLICYENGINE_US_VERSION, POLICYENGINE_UK_VERSION
#
# Deploys two apps:
# 1. policyengine-simulation-gateway - Stable gateway with fixed URL
# 2. policyengine-simulation-us{X}-uk{Y} - Versioned simulation app

set -euo pipefail

MODAL_ENV="${1:?Modal environment required}"

# Generate versioned simulation app name (dots replaced with dashes for URL safety)
US_VERSION_SAFE="${POLICYENGINE_US_VERSION//./-}"
UK_VERSION_SAFE="${POLICYENGINE_UK_VERSION//./-}"
SIMULATION_APP_NAME="policyengine-simulation-us${US_VERSION_SAFE}-uk${UK_VERSION_SAFE}"

echo "========================================"
echo "Deploying to Modal environment: $MODAL_ENV"
echo "  US version: ${POLICYENGINE_US_VERSION}"
echo "  UK version: ${POLICYENGINE_UK_VERSION}"
echo "========================================"

# 1. Deploy the gateway app (stable URL)
echo ""
echo "Step 1: Deploying gateway app..."
echo "  App name: policyengine-simulation-gateway"
uv run modal deploy --env="$MODAL_ENV" src/modal/gateway/app.py

# 2. Deploy the versioned simulation app
echo ""
echo "Step 2: Deploying versioned simulation app..."
echo "  App name: ${SIMULATION_APP_NAME}"
export MODAL_APP_NAME="$SIMULATION_APP_NAME"
uv run modal deploy --env="$MODAL_ENV" src/modal/app.py

# 3. Update version registries
echo ""
echo "Step 3: Updating version registries..."
uv run python -m src.modal.utils.update_version_registry \
    --app-name "$SIMULATION_APP_NAME" \
    --us-version "${POLICYENGINE_US_VERSION}" \
    --uk-version "${POLICYENGINE_UK_VERSION}" \
    --environment "$MODAL_ENV"

echo ""
echo "========================================"
echo "Deployment complete!"
echo "  Gateway app: policyengine-simulation-gateway"
echo "  Simulation app: $SIMULATION_APP_NAME"
echo "========================================"
