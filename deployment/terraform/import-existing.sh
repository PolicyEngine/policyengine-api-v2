#!/bin/bash
# Script to import existing GCP resources into terraform state

# Source environment
if [ -f "../.env" ]; then
    export $(cat ../.env | grep -v '^#' | xargs)
fi

PROJECT_ID="${PROJECT_ID:-beta-api-v2-1b3f}"
REGION="${REGION:-us-central1}"

echo "Importing existing resources into terraform state for project: $PROJECT_ID"

# Generate auto.tfvars file with required variables
US_VERSION=$(grep -A1 'name = "policyengine-us"' ../../projects/policyengine-api-simulation/uv.lock | grep version | head -1 | sed 's/.*"\(.*\)".*/\1/')
UK_VERSION=$(grep -A1 'name = "policyengine-uk"' ../../projects/policyengine-api-simulation/uv.lock | grep version | head -1 | sed 's/.*"\(.*\)".*/\1/')
COMMIT_URL="https://github.com/PolicyEngine/policyengine-api-v2/commit/$(cd ../.. && git rev-parse HEAD)"

cat > infra/auto.tfvars <<EOF
project_id = "$PROJECT_ID"
commit_url = "$COMMIT_URL"
policyengine-us-package-version = "$US_VERSION"
policyengine-uk-package-version = "$UK_VERSION"
is_prod = ${TF_VAR_is_prod:-false}
full_container_tag = "${TF_VAR_full_container_tag:-latest}"
simulation_container_tag = "${TF_VAR_simulation_container_tag:-latest}"
tagger_container_tag = "${TF_VAR_tagger_container_tag:-latest}"
region = "$REGION"
stage = "${TF_VAR_stage:-dev}"
EOF

cd infra

echo "=== Importing Service Accounts ==="
terraform import -var-file=auto.tfvars google_service_account.workflow_sa projects/$PROJECT_ID/serviceAccounts/simulation-workflows-sa@$PROJECT_ID.iam.gserviceaccount.com 2>/dev/null || echo "  workflow_sa already imported or doesn't exist"
terraform import -var-file=auto.tfvars module.cloud_run_tagger_api.google_service_account.api projects/$PROJECT_ID/serviceAccounts/tagger-api@$PROJECT_ID.iam.gserviceaccount.com 2>/dev/null || echo "  tagger-api SA already imported or doesn't exist"
terraform import -var-file=auto.tfvars module.cloud_run_full_api.google_service_account.api projects/$PROJECT_ID/serviceAccounts/full-api@$PROJECT_ID.iam.gserviceaccount.com 2>/dev/null || echo "  full-api SA already imported or doesn't exist"
terraform import -var-file=auto.tfvars module.cloud_run_simulation_api.google_service_account.api projects/$PROJECT_ID/serviceAccounts/api-simulation@$PROJECT_ID.iam.gserviceaccount.com 2>/dev/null || echo "  api-simulation SA already imported or doesn't exist"

echo "=== Importing IAM Roles ==="
terraform import -var-file=auto.tfvars google_project_iam_custom_role.cloudrun_service_updater projects/$PROJECT_ID/roles/cloudRunServiceUpdater 2>/dev/null || echo "  Custom role already imported or doesn't exist"

echo "=== Importing Storage Buckets ==="
terraform import -var-file=auto.tfvars google_storage_bucket.metadata $PROJECT_ID-metadata 2>/dev/null || echo "  Metadata bucket already imported or doesn't exist"

echo "=== Importing Cloud Run Services ==="
terraform import -var-file=auto.tfvars module.cloud_run_tagger_api.google_cloud_run_v2_service.api projects/$PROJECT_ID/locations/$REGION/services/tagger-api 2>/dev/null || echo "  tagger-api service already imported or doesn't exist"
terraform import -var-file=auto.tfvars module.cloud_run_full_api.google_cloud_run_v2_service.api projects/$PROJECT_ID/locations/$REGION/services/full-api 2>/dev/null || echo "  full-api service already imported or doesn't exist"
terraform import -var-file=auto.tfvars module.cloud_run_simulation_api.google_cloud_run_v2_service.api projects/$PROJECT_ID/locations/$REGION/services/api-simulation 2>/dev/null || echo "  api-simulation service already imported or doesn't exist"

echo "=== Handling Workflows ==="
echo "Note: Workflows don't support terraform import."
echo "If you see 'already exists' errors for workflows, you have two options:"
echo "  1. Delete the existing workflows manually and let terraform recreate them"
echo "  2. Import them into state manually (advanced)"

# Check if workflows exist
if gcloud workflows list --location=$REGION --project=$PROJECT_ID 2>/dev/null | grep -q "wait-for-country-packages"; then
    echo "⚠️  Found existing workflow: wait-for-country-packages"
    echo "   To resolve: gcloud workflows delete wait-for-country-packages --location=$REGION --project=$PROJECT_ID"
fi

if gcloud workflows list --location=$REGION --project=$PROJECT_ID 2>/dev/null | grep -q "simulation-workflow"; then
    echo "⚠️  Found existing workflow: simulation-workflow"
    echo "   To resolve: gcloud workflows delete simulation-workflow --location=$REGION --project=$PROJECT_ID"
fi

echo ""
echo "✅ Import process complete!"
echo ""
echo "Next steps:"
echo "  1. If you see workflow conflicts above, delete them with the provided commands"
echo "  2. Run 'make terraform-deploy' to deploy/update infrastructure"