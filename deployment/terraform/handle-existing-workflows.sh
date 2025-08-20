#!/bin/bash
# Script to handle existing workflows before terraform deployment

set -e

# Get project ID from command line or environment
PROJECT_ID="${1:-${TF_VAR_project_id}}"
REGION="${2:-${TF_VAR_region:-us-central1}}"

if [ -z "$PROJECT_ID" ]; then
    echo "Usage: $0 <project_id> [region]"
    echo "Or set TF_VAR_project_id environment variable"
    exit 1
fi

echo "Checking for existing workflows in project: $PROJECT_ID, region: $REGION"

# Check if workflows exist
EXISTING_WORKFLOWS=$(gcloud workflows list --location="$REGION" --project="$PROJECT_ID" --format="value(name)" 2>/dev/null || true)

# Check for our specific workflows
for workflow in "simulation-workflow" "wait-for-country-packages"; do
    if echo "$EXISTING_WORKFLOWS" | grep -q "$workflow"; then
        echo "Found existing workflow: $workflow"
        echo "Options:"
        echo "  1. Delete the workflow manually:"
        echo "     gcloud workflows delete $workflow --location=$REGION --project=$PROJECT_ID"
        echo ""
        echo "  2. Or use terraform import (but this may not work with all configurations):"
        echo "     cd deployment/terraform/infra"
        echo "     terraform import google_workflows_workflow.$(echo $workflow | tr '-' '_') projects/$PROJECT_ID/locations/$REGION/workflows/$workflow"
        echo ""
        FOUND_EXISTING=true
    fi
done

if [ "$FOUND_EXISTING" = true ]; then
    echo ""
    echo "⚠️  Existing workflows found. You have two options:"
    echo ""
    echo "Option A: Delete existing workflows and let terraform recreate them"
    echo "  Run: $0 $PROJECT_ID $REGION --delete"
    echo ""
    echo "Option B: Keep existing workflows (may cause deployment to fail)"
    echo "  Continue with deployment and handle errors manually"
    echo ""
    
    # Check for --delete flag
    if [ "$3" = "--delete" ]; then
        echo "Deleting existing workflows..."
        for workflow in "simulation-workflow" "wait-for-country-packages"; do
            if echo "$EXISTING_WORKFLOWS" | grep -q "$workflow"; then
                echo "Deleting $workflow..."
                gcloud workflows delete "$workflow" --location="$REGION" --project="$PROJECT_ID" --quiet || true
            fi
        done
        echo "✅ Workflows deleted. You can now run terraform deployment."
    else
        exit 1
    fi
else
    echo "✅ No conflicting workflows found. Safe to proceed with terraform deployment."
fi