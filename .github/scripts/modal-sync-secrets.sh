#!/bin/bash
# Sync secrets from GitHub to Modal environment
# Usage: ./modal-sync-secrets.sh <modal-environment> <gh-environment>
# Required env vars:
#   LOGFIRE_TOKEN
#   GCP_CREDENTIALS_JSON (optional)
#   OBSERVABILITY_ENABLED (optional, defaults to false)
#   OBSERVABILITY_SHADOW_MODE (optional, defaults to true)
#   OBSERVABILITY_OTLP_ENDPOINT (required when OBSERVABILITY_ENABLED=true)
#   OBSERVABILITY_OTLP_HEADERS (required when OBSERVABILITY_ENABLED=true)

set -euo pipefail

MODAL_ENV="${1:?Modal environment required}"
GH_ENV="${2:?GitHub environment required}"
OBSERVABILITY_ENABLED="${OBSERVABILITY_ENABLED:-false}"
OBSERVABILITY_SHADOW_MODE="${OBSERVABILITY_SHADOW_MODE:-true}"

echo "Syncing secrets to Modal environment: $MODAL_ENV"

# Sync Logfire secret
uv run modal secret create policyengine-logfire \
  "LOGFIRE_TOKEN=${LOGFIRE_TOKEN:-}" \
  "LOGFIRE_ENVIRONMENT=$GH_ENV" \
  --env="$MODAL_ENV" \
  --force || true

# Sync GCP credentials if provided
if [ -n "${GCP_CREDENTIALS_JSON:-}" ]; then
  uv run modal secret create gcp-credentials \
    "GOOGLE_APPLICATION_CREDENTIALS_JSON=$GCP_CREDENTIALS_JSON" \
    --env="$MODAL_ENV" \
    --force || true
fi

if [ "$OBSERVABILITY_ENABLED" = "true" ]; then
  : "${OBSERVABILITY_OTLP_ENDPOINT:?OBSERVABILITY_OTLP_ENDPOINT is required when observability is enabled}"
  : "${OBSERVABILITY_OTLP_HEADERS:?OBSERVABILITY_OTLP_HEADERS is required when observability is enabled}"
fi

uv run modal secret create policyengine-observability \
  "OBSERVABILITY_ENABLED=$OBSERVABILITY_ENABLED" \
  "OBSERVABILITY_SHADOW_MODE=$OBSERVABILITY_SHADOW_MODE" \
  "OBSERVABILITY_ENVIRONMENT=$GH_ENV" \
  "OBSERVABILITY_OTLP_ENDPOINT=${OBSERVABILITY_OTLP_ENDPOINT:-}" \
  "OBSERVABILITY_OTLP_HEADERS=${OBSERVABILITY_OTLP_HEADERS:-}" \
  --env="$MODAL_ENV" \
  --force || true

echo "Modal secrets synced"
