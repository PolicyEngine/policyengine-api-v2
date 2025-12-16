#!/bin/bash
#
# Restore tags from backup file.
#
# Usage:
#   ./scripts/restore-tags-from-backup.sh [backup_file]
#
# Arguments:
#   backup_file - Path to backup file (default: scripts/beta_tags_backup.txt)
#
# The backup file should contain lines in format: tag=revision
#

set -euo pipefail

PROJECT="beta-api-v2-1b3f"
REGION="us-central1"
SERVICE="api-simulation"
BACKUP_FILE="${1:-scripts/beta_tags_backup.txt}"

if [ ! -f "$BACKUP_FILE" ]; then
    echo "ERROR: Backup file not found: $BACKUP_FILE"
    exit 1
fi

echo "=========================================="
echo "Restoring tags from backup"
echo "=========================================="
echo ""
echo "Project: $PROJECT"
echo "Backup file: $BACKUP_FILE"
echo ""

# Read all tags from backup and build the --set-tags argument
TAGS=""
while IFS= read -r line; do
    if [ -n "$line" ]; then
        if [ -n "$TAGS" ]; then
            TAGS="${TAGS},${line}"
        else
            TAGS="$line"
        fi
    fi
done < "$BACKUP_FILE"

TAG_COUNT=$(echo "$TAGS" | tr ',' '\n' | wc -l)
echo "Restoring $TAG_COUNT tags..."
echo ""

# Restore all tags in one command
gcloud run services update-traffic "$SERVICE" \
    --project="$PROJECT" \
    --region="$REGION" \
    --set-tags="$TAGS"

echo ""
echo "=========================================="
echo "Restoration complete!"
echo "=========================================="

# Verify
NEW_TAGS=$(gcloud run services describe "$SERVICE" \
  --project="$PROJECT" \
  --region="$REGION" \
  --format="json(status.traffic)" | jq '[.status.traffic[] | select(.tag != null)] | length')
echo "Tags now present: $NEW_TAGS"
