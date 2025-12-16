#!/bin/bash
#
# Calls the tagger API cleanup endpoint to remove old traffic tags and metadata.
#
# Usage:
#   ./scripts/cleanup-old-revisions.sh <tagger_url> <token> [keep_count]
#
# Arguments:
#   tagger_url  - Full URL of the tagger API (e.g., "https://tagger-api-xxx.run.app")
#   token       - ID token for authentication
#   keep_count  - Number of recent deployments to keep (default: 40)
#
# The script:
# 1. Calls POST /cleanup?keep=N on the tagger API
# 2. Reports results (but doesn't fail the deployment on cleanup errors)
#

set -euo pipefail

TAGGER_URL="$1"
TOKEN="$2"
KEEP_COUNT="${3:-40}"

echo "Calling cleanup endpoint on tagger API"
echo "  URL: ${TAGGER_URL}/cleanup?keep=${KEEP_COUNT}"

# Call cleanup endpoint
RESPONSE=$(curl -s -w "\n%{http_code}" -X POST \
    "${TAGGER_URL}/cleanup?keep=${KEEP_COUNT}" \
    -H "Authorization: Bearer $TOKEN" \
    -H "Content-Type: application/json")

HTTP_CODE=$(echo "$RESPONSE" | tail -n1)
BODY=$(echo "$RESPONSE" | sed '$d')

if [ "$HTTP_CODE" -ge 200 ] && [ "$HTTP_CODE" -lt 300 ]; then
    echo "Cleanup successful (HTTP $HTTP_CODE):"
    echo "$BODY" | jq .

    # Extract and display summary
    KEPT=$(echo "$BODY" | jq -r '.revisions_kept | length')
    TAGS_REMOVED=$(echo "$BODY" | jq -r '.tags_removed | length')
    FILES_DELETED=$(echo "$BODY" | jq -r '.metadata_files_deleted | length')
    ERRORS=$(echo "$BODY" | jq -r '.errors | length')

    echo ""
    echo "Summary:"
    echo "  Revisions kept: $KEPT"
    echo "  Tags removed: $TAGS_REMOVED"
    echo "  Metadata files deleted: $FILES_DELETED"
    echo "  Errors: $ERRORS"

    if [ "$ERRORS" -gt 0 ]; then
        echo ""
        echo "Warnings during cleanup:"
        echo "$BODY" | jq -r '.errors[]'
    fi
else
    echo "Cleanup failed with HTTP $HTTP_CODE:"
    echo "$BODY"
    # Don't fail the deployment if cleanup fails - it's not critical
    echo "::warning::Cleanup failed but deployment succeeded. Review logs for details."
fi
