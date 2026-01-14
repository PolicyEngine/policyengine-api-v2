#!/bin/bash
# Get the deployed Modal gateway URL
# Usage: ./modal-get-url.sh <modal-environment>
# Outputs: Sets simulation_api_url in GITHUB_OUTPUT
#
# Returns the stable gateway URL (policyengine-simulation-gateway)

set -euo pipefail

MODAL_ENV="${1:?Modal environment required}"
GATEWAY_APP_NAME="policyengine-simulation-gateway"
FUNCTION_NAME="web-app"

# Construct URL based on environment
# URL format:
#   main: https://policyengine--<app-name>-<function-name>.modal.run
#   other: https://policyengine-<env>--<app-name>-<function-name>.modal.run
if [ "$MODAL_ENV" = "main" ]; then
  SIMULATION_URL="https://policyengine--${GATEWAY_APP_NAME}-${FUNCTION_NAME}.modal.run"
else
  SIMULATION_URL="https://policyengine-${MODAL_ENV}--${GATEWAY_APP_NAME}-${FUNCTION_NAME}.modal.run"
fi

echo "simulation_api_url=$SIMULATION_URL" >> "$GITHUB_OUTPUT"
echo "Gateway URL: $SIMULATION_URL"
