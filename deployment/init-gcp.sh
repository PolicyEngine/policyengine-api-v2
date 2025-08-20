#!/bin/bash
# Quick GCP initialization script

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Source .env file
if [ ! -f "deployment/.env" ]; then
    echo -e "${RED}Error: deployment/.env not found${NC}"
    echo "Run 'make setup' first"
    exit 1
fi

source deployment/.env

echo -e "${GREEN}Initializing GCP for PolicyEngine API${NC}"
echo "Project ID: $PROJECT_ID"
echo "Region: $REGION"

# Check if logged in
echo -e "\n${YELLOW}Checking GCP authentication...${NC}"
if ! gcloud auth list --filter=status:ACTIVE --format="value(account)" | grep -q .; then
    echo "Not logged in to GCP. Running 'gcloud auth login'..."
    gcloud auth login
fi

# Set project
echo -e "\n${YELLOW}Setting GCP project...${NC}"
gcloud config set project $PROJECT_ID

# Enable required APIs
echo -e "\n${YELLOW}Enabling required GCP APIs...${NC}"
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
    --project=$PROJECT_ID

# Create Artifact Registry if it doesn't exist
echo -e "\n${YELLOW}Creating Artifact Registry repository...${NC}"
gcloud artifacts repositories create $REPO \
    --repository-format=docker \
    --location=$REGION \
    --description="PolicyEngine API Docker images" \
    --project=$PROJECT_ID 2>/dev/null || echo "Repository already exists"

# Configure Docker
echo -e "\n${YELLOW}Configuring Docker authentication...${NC}"
gcloud auth configure-docker $REGION-docker.pkg.dev

# Create terraform state bucket
echo -e "\n${YELLOW}Creating Terraform state bucket...${NC}"
gcloud storage buckets create gs://$PROJECT_ID-state \
    --project=$PROJECT_ID \
    --location=$REGION \
    --uniform-bucket-level-access 2>/dev/null || echo "Bucket already exists"
gcloud storage buckets update gs://$PROJECT_ID-state --versioning

echo -e "\n${GREEN}✅ GCP initialization complete!${NC}"
echo -e "\nNext steps:"
echo "  1. Run 'make build-prod' to build Docker images"
echo "  2. Run 'make deploy' to deploy to GCP"