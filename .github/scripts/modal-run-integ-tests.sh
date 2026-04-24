#!/bin/bash
# Run simulation integration tests
# Usage: ./modal-run-integ-tests.sh <environment> <base-url> [us-version]
# Environment: beta runs all tests, prod excludes beta_only tests
#
# Required env vars (set in the calling workflow from org-wide GH secrets):
#   GATEWAY_AUTH_ISSUER, GATEWAY_AUTH_AUDIENCE,
#   GATEWAY_AUTH_CLIENT_ID, GATEWAY_AUTH_CLIENT_SECRET
# Used to fetch an Auth0 client_credentials token that the pytest client
# sends as Authorization: Bearer on every call to the gated gateway.

set -euo pipefail

ENVIRONMENT="${1:?Environment required (beta or prod)}"
BASE_URL="${2:?Base URL required}"
US_VERSION="${3:-}"

: "${GATEWAY_AUTH_ISSUER:?GATEWAY_AUTH_ISSUER is required to mint an integ-test token}"
: "${GATEWAY_AUTH_AUDIENCE:?GATEWAY_AUTH_AUDIENCE is required to mint an integ-test token}"
: "${GATEWAY_AUTH_CLIENT_ID:?GATEWAY_AUTH_CLIENT_ID is required to mint an integ-test token}"
: "${GATEWAY_AUTH_CLIENT_SECRET:?GATEWAY_AUTH_CLIENT_SECRET is required to mint an integ-test token}"

ISSUER="${GATEWAY_AUTH_ISSUER%/}"
TOKEN_URL="$ISSUER/oauth/token"

# Build the token-request JSON with Python so that any ", \, or newline in
# the client secret is encoded correctly (Auth0-generated secrets are
# random strings that routinely contain characters that break a shell
# heredoc).
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

cd projects/policyengine-apis-integ
uv sync --extra test

export simulation_integ_test_base_url="$BASE_URL"
export simulation_integ_test_access_token="$ACCESS_TOKEN"

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
