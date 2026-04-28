#!/bin/bash
# Run simulation integration tests
# Usage: ./modal-run-integ-tests.sh <environment> <base-url> [us-version]
# Environment: beta runs all tests, prod excludes beta_only tests

set -euo pipefail

ENVIRONMENT="${1:?Environment required (beta or prod)}"
BASE_URL="${2:?Base URL required}"
US_VERSION="${3:-}"

truthy() {
  case "${1:-}" in
    1|true|TRUE|yes|YES|on|ON) return 0 ;;
    *) return 1 ;;
  esac
}

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
  echo "Gateway auth integration-test config is partial." >&2
  echo "  Present: ${present[*]-}" >&2
  echo "  Missing: ${missing[*]-}" >&2
  exit 1
fi

SHOULD_MINT_TOKEN=0
if truthy "${GATEWAY_AUTH_REQUIRED:-}"; then
  if [ ${#missing[@]} -gt 0 ]; then
    echo "GATEWAY_AUTH_REQUIRED is enabled but integration-test auth secrets are missing." >&2
    echo "  Missing: ${missing[*]-}" >&2
    exit 1
  fi
  SHOULD_MINT_TOKEN=1
elif [ ${#present[@]} -eq ${#GATEWAY_AUTH_VARS[@]} ]; then
  SHOULD_MINT_TOKEN=1
fi

ACCESS_TOKEN=""
if [ "$SHOULD_MINT_TOKEN" -eq 1 ]; then
  ISSUER="${GATEWAY_AUTH_ISSUER%/}"
  TOKEN_URL="$ISSUER/oauth/token"

  # Build the token-request JSON with Python so that any ", \, or newline in
  # the client secret is encoded correctly (Auth0-generated secrets are random
  # strings that routinely contain characters that break a shell heredoc).
  TOKEN_REQUEST_JSON=$(
    CLIENT_ID="$GATEWAY_AUTH_CLIENT_ID" \
    CLIENT_SECRET="$GATEWAY_AUTH_CLIENT_SECRET" \
    AUDIENCE="$GATEWAY_AUTH_AUDIENCE" \
    python3 -c '
import json, os
print(json.dumps({
    "client_id": os.environ["CLIENT_ID"],
    "client_secret": os.environ["CLIENT_SECRET"],
    "audience": os.environ["AUDIENCE"],
    "grant_type": "client_credentials",
}))
'
  )

  echo "Requesting client_credentials access token from $TOKEN_URL"
  TOKEN_RESPONSE=$(
    curl --fail-with-body --silent --show-error \
      --request POST "$TOKEN_URL" \
      --header "content-type: application/json" \
      --data-binary "$TOKEN_REQUEST_JSON"
  )

  ACCESS_TOKEN=$(
    printf '%s' "$TOKEN_RESPONSE" | python3 -c '
import json, sys
data = json.load(sys.stdin)
token = data.get("access_token")
if not token:
    sys.exit(f"Auth0 response missing access_token: {data}")
print(token)
'
  )
  if [ -z "$ACCESS_TOKEN" ]; then
    echo "Failed to extract access_token from Auth0 response" >&2
    exit 1
  fi
fi

cd projects/policyengine-apis-integ
uv sync --extra test

export simulation_integ_test_base_url="$BASE_URL"
export simulation_integ_test_gateway_auth_required="${GATEWAY_AUTH_REQUIRED:-}"

if [ -n "$ACCESS_TOKEN" ]; then
  export simulation_integ_test_access_token="$ACCESS_TOKEN"
fi

if [ -n "$US_VERSION" ]; then
  export simulation_integ_test_us_model_version="$US_VERSION"
fi

if [ "$ENVIRONMENT" = "beta" ]; then
  echo "Running all simulation integration tests (including beta_only)"
  uv run pytest tests/simulation/ -v
else
  echo "Running simulation integration tests (excluding beta_only)"
  uv run pytest tests/simulation/ -v -m "not beta_only"
fi
