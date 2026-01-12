#!/bin/bash
# Get the deployed Modal app URL
# Usage: ./modal-get-url.sh <modal-environment> <app-name> <function-name>
# Outputs: Sets simulation_api_url in GITHUB_OUTPUT

set -euo pipefail

MODAL_ENV="${1:?Modal environment required}"
APP_NAME="${2:-policyengine-simulation}"
FUNCTION_NAME="${3:-web-app}"

# Try to get URL from Modal app list
APP_INFO=$(uv run modal app list --env="$MODAL_ENV" --json 2>/dev/null | jq -r ".[] | select(.name == \"$APP_NAME\")" || echo "")

SIMULATION_URL=""
if [ -n "$APP_INFO" ]; then
  SIMULATION_URL=$(echo "$APP_INFO" | jq -r '.web_urls[0] // empty' 2>/dev/null || echo "")
fi

# If we couldn't get the URL from app info, construct it based on environment
if [ -z "$SIMULATION_URL" ]; then
  # URL format:
  #   main: https://<workspace>--<app-name>-<function-name>.modal.run
  #   other: https://<workspace>-<env>--<app-name>-<function-name>.modal.run
  if [ "$MODAL_ENV" = "main" ]; then
    SIMULATION_URL="https://policyengine--${APP_NAME}-${FUNCTION_NAME}.modal.run"
  else
    SIMULATION_URL="https://policyengine-${MODAL_ENV}--${APP_NAME}-${FUNCTION_NAME}.modal.run"
  fi
fi

echo "simulation_api_url=$SIMULATION_URL" >> "$GITHUB_OUTPUT"
echo "Deployed simulation API URL: $SIMULATION_URL"
