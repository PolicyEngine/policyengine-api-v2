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
#
# Fail loud if some but not all of the four GH secrets are present — a
# partial config would silently leave the Modal secret stale or missing,
# which surfaces as 503s from /require_auth on every gated request.
GATEWAY_AUTH_VARS=(
  GATEWAY_AUTH_ISSUER
  GATEWAY_AUTH_AUDIENCE
  GATEWAY_AUTH_CLIENT_ID
  GATEWAY_AUTH_CLIENT_SECRET
)
present=()
missing=()
for var in "${GATEWAY_AUTH_VARS[@]}"; do
  if [ -n "${!var:-}" ]; then
    present+=("$var")
  else
    missing+=("$var")
  fi
done

if [ ${#present[@]} -gt 0 ] && [ ${#missing[@]} -gt 0 ]; then
  echo "Partial GATEWAY_AUTH_* GitHub secrets detected." >&2
  echo "  Present: ${present[*]}" >&2
  echo "  Missing: ${missing[*]}" >&2
  echo "Refusing to write a partial gateway-auth Modal secret." >&2
  exit 1
fi

if [ ${#present[@]} -eq ${#GATEWAY_AUTH_VARS[@]} ]; then
  # Auth0 issuer strings are expected to end with "/" to match the `iss`
  # claim and JWKS-url construction on the verifier side. Normalize here
  # so an operator who stored the GH secret without the trailing slash
  # doesn't silently break JWT validation on every gated call.
  NORMALIZED_ISSUER="$GATEWAY_AUTH_ISSUER"
  case "$NORMALIZED_ISSUER" in
    */) ;;
    *) NORMALIZED_ISSUER="$NORMALIZED_ISSUER/" ;;
  esac

  uv run modal secret create gateway-auth \
    "GATEWAY_AUTH_ISSUER=$NORMALIZED_ISSUER" \
    "GATEWAY_AUTH_AUDIENCE=$GATEWAY_AUTH_AUDIENCE" \
    "GATEWAY_AUTH_CLIENT_ID=$GATEWAY_AUTH_CLIENT_ID" \
    "GATEWAY_AUTH_CLIENT_SECRET=$GATEWAY_AUTH_CLIENT_SECRET" \
    --env="$MODAL_ENV" \
    --force
fi

echo "Modal secrets synced"
