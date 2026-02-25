#!/bin/bash
# Run simulation integration tests
# Usage: ./modal-run-integ-tests.sh <environment> <base-url> [us-version]
# Environment: beta runs all tests, prod excludes beta_only tests

set -euo pipefail

ENVIRONMENT="${1:?Environment required (beta or prod)}"
BASE_URL="${2:?Base URL required}"
US_VERSION="${3:-}"

cd projects/policyengine-apis-integ
uv sync --extra test

export simulation_integ_test_base_url="$BASE_URL"

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
