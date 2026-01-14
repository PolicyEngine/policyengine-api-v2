#!/bin/bash
# Verify Modal deployment health with retries
# Usage: ./modal-health-check.sh <base-url> [max-attempts] [sleep-seconds]

set -euo pipefail

BASE_URL="${1:?Base URL required}"
MAX_ATTEMPTS="${2:-5}"
SLEEP_SECONDS="${3:-10}"

HEALTH_URL="${BASE_URL}/health"
echo "Checking health at: $HEALTH_URL"

for i in $(seq 1 "$MAX_ATTEMPTS"); do
  if curl -sf "$HEALTH_URL" > /dev/null 2>&1; then
    echo "Health check passed!"
    curl -s "$HEALTH_URL" | jq .
    exit 0
  fi
  echo "Attempt $i/$MAX_ATTEMPTS: Waiting for deployment to be ready..."
  sleep "$SLEEP_SECONDS"
done

echo "Health check failed after $MAX_ATTEMPTS attempts"
exit 1
