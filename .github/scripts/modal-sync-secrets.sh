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

# Sync gateway auth secret. The gateway container consumes issuer+audience to
# validate bearer tokens; client_id/secret are stored alongside so rotating the
# Auth0 M2M app updates every consumer from one place.
if [ -n "${GATEWAY_AUTH_ISSUER:-}" ] \
  && [ -n "${GATEWAY_AUTH_AUDIENCE:-}" ] \
  && [ -n "${GATEWAY_AUTH_CLIENT_ID:-}" ] \
  && [ -n "${GATEWAY_AUTH_CLIENT_SECRET:-}" ]; then
  uv run modal secret create gateway-auth \
    "GATEWAY_AUTH_ISSUER=$GATEWAY_AUTH_ISSUER" \
    "GATEWAY_AUTH_AUDIENCE=$GATEWAY_AUTH_AUDIENCE" \
    "GATEWAY_AUTH_CLIENT_ID=$GATEWAY_AUTH_CLIENT_ID" \
    "GATEWAY_AUTH_CLIENT_SECRET=$GATEWAY_AUTH_CLIENT_SECRET" \
    --env="$MODAL_ENV" \
    --force || true
fi

echo "Modal secrets synced"
