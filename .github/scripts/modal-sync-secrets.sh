#!/bin/bash
# Sync secrets from GitHub to Modal environment
# Usage: ./modal-sync-secrets.sh <modal-environment> <gh-environment>
# Required env vars: LOGFIRE_TOKEN, GCP_CREDENTIALS_JSON (optional)

set -euo pipefail

MODAL_ENV="${1:?Modal environment required}"
GH_ENV="${2:?GitHub environment required}"

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

# Sync gateway auth config. Empty values preserve the existing public-gateway
# behavior unless GATEWAY_AUTH_REQUIRED is explicitly set.
uv run modal secret create policyengine-gateway-auth \
  "GATEWAY_AUTH_ISSUER=${GATEWAY_AUTH_ISSUER:-}" \
  "GATEWAY_AUTH_AUDIENCE=${GATEWAY_AUTH_AUDIENCE:-}" \
  "GATEWAY_AUTH_REQUIRED=${GATEWAY_AUTH_REQUIRED:-}" \
  --env="$MODAL_ENV" \
  --force || true

echo "Modal secrets synced"
