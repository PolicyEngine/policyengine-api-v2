# Setting up terraform for a new GCP project

This guide walks through deploying PolicyEngine API to a new GCP project.

## Prerequisites

1. **GCP account** with billing enabled
2. **gcloud CLI** installed and authenticated
3. **Terraform** installed (v1.0+)
4. **Docker** installed for building images
5. **Appropriate IAM permissions** to create projects and resources

## Step 1: Create and configure GCP project

### Option A: Create new project via terraform
```bash
# Configure project variables
cd deployment/terraform/project
cp apply.example.tfvars terraform.tfvars

# Edit terraform.tfvars with your details:
# - org_id: Your GCP organization ID
# - billing_account: Your billing account ID
# - stage: Environment name (e.g., "prod", "staging", "dev")
# - project_name: Base name for the project

# Initialize and apply
terraform init
terraform apply
```

### Option B: Use existing project
Skip the project creation and note your existing project ID.

## Step 2: Set up terraform state backend

```bash
# Create a GCS bucket for terraform state
export PROJECT_ID="your-project-id"
export BUCKET_NAME="${PROJECT_ID}-state"
export REGION="us-central1"

# Using gcloud storage (works with Python 3.13+)
gcloud storage buckets create gs://${BUCKET_NAME} \
  --project=${PROJECT_ID} \
  --location=${REGION} \
  --uniform-bucket-level-access

gcloud storage buckets update gs://${BUCKET_NAME} --versioning

# Configure backend for both modules
cd deployment/terraform/project
cp backend.example.tf backend.tf
# Edit backend.tf and set bucket = "your-project-id-state"

cd ../infra
cp backend.example.tfvars backend.tfvars
# Edit backend.tfvars and set bucket = "your-project-id-state"
```

## Step 3: Enable required APIs

```bash
gcloud services enable \
  artifactregistry.googleapis.com \
  cloudbuild.googleapis.com \
  compute.googleapis.com \
  run.googleapis.com \
  cloudresourcemanager.googleapis.com \
  serviceusage.googleapis.com \
  workflows.googleapis.com \
  cloudtrace.googleapis.com \
  monitoring.googleapis.com \
  secretmanager.googleapis.com \
  --project=${PROJECT_ID}
```

## Step 4: Create Artifact Registry repository

```bash
# Create Docker repository for container images
gcloud artifacts repositories create api-v2 \
  --repository-format=docker \
  --location=us-central1 \
  --description="PolicyEngine API Docker images" \
  --project=${PROJECT_ID}

# Configure Docker authentication
gcloud auth configure-docker us-central1-docker.pkg.dev
```

## Step 5: Build and push Docker images

```bash
# Set environment variables
export PROJECT_ID="your-project-id"
export REGION="us-central1"
export REPO="api-v2"
export TAG="initial"

# Build and push images
cd /path/to/policyengine-api-v2
make build-prod
make push-images
```

## Step 6: Deploy infrastructure

```bash
cd deployment/terraform/infra

# Configure variables
cp apply.example.tfvars terraform.tfvars
# Edit terraform.tfvars:
# - project_id: Your GCP project ID
# - region: Target region (e.g., "us-central1")
# - stage: Environment name
# - is_prod: true for production, false otherwise
# - container tags for each service

# Initialize and deploy
terraform init -backend-config="bucket=${PROJECT_ID}-state"
terraform plan
terraform apply
```

## Step 7: Configure secrets (if needed)

```bash
# Add any required secrets to Secret Manager
gcloud secrets create hugging-face-token \
  --data-file=path/to/token.txt \
  --project=${PROJECT_ID}

# Grant service account access
gcloud secrets add-iam-policy-binding hugging-face-token \
  --member="serviceAccount:simulation-workflows-sa@${PROJECT_ID}.iam.gserviceaccount.com" \
  --role="roles/secretmanager.secretAccessor" \
  --project=${PROJECT_ID}
```

## Step 8: Verify deployment

```bash
# List deployed services
gcloud run services list --project=${PROJECT_ID}

# Get service URLs
gcloud run services describe full-api \
  --region=${REGION} \
  --project=${PROJECT_ID} \
  --format="value(status.url)"

# Test endpoints
curl $(gcloud run services describe full-api \
  --region=${REGION} \
  --project=${PROJECT_ID} \
  --format="value(status.url)")/ping/alive
```

## Environment-specific configurations

### Development
- Set `is_prod = false` in terraform.tfvars
- Minimum instances set to 0 (scale to zero)
- Relaxed concurrency limits

### Production
- Set `is_prod = true` in terraform.tfvars
- Minimum instances kept warm (min_instance_count = 1)
- Configure monitoring and alerting
- Set up custom domain (optional)

## Updating deployments

For subsequent deployments to the same project:

```bash
# Update code and rebuild images
export TAG="v1.2.3"  # or git commit SHA
make build-prod
make push-images

# Update terraform with new image tags
cd deployment/terraform/infra
# Edit terraform.tfvars with new container tags
terraform apply
```

## Cleanup

To tear down all resources:

```bash
cd deployment/terraform/infra
terraform destroy

cd ../project
terraform destroy  # Only if you created the project via terraform
```

## Troubleshooting

### Authentication issues
```bash
gcloud auth application-default login
gcloud config set project ${PROJECT_ID}
```

### Terraform state issues
```bash
# Force unlock if state is locked
terraform force-unlock <lock-id>

# Refresh state
terraform refresh
```

### Service deployment issues
```bash
# Check Cloud Run logs
gcloud run services logs read full-api \
  --region=${REGION} \
  --project=${PROJECT_ID}

# Check service details
gcloud run services describe full-api \
  --region=${REGION} \
  --project=${PROJECT_ID}
```

## Required IAM roles

Ensure your account has these roles:
- `roles/resourcemanager.projectCreator` (if creating new project)
- `roles/billing.user`
- `roles/iam.serviceAccountAdmin`
- `roles/run.admin`
- `roles/artifactregistry.admin`
- `roles/workflows.admin`
- `roles/storage.admin` (for terraform state)