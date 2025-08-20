# Terraform infrastructure

Two terraform modules for deploying PolicyEngine API:

## Modules

- `project/` - GCP project setup and configuration
- `infra/` - Cloud Run services and infrastructure

## Usage

```bash
# Initialize terraform
make terraform-init

# Plan changes
make terraform-plan

# Deploy infrastructure
make terraform-deploy
```

## Configuration

1. Copy example files:
```bash
cp project/apply.example.tfvars project/terraform.tfvars
cp infra/apply.example.tfvars infra/terraform.tfvars
```

2. Update the `.tfvars` files with your GCP project details

3. Backend storage is automatically configured when you run `make terraform-init`
   - Creates GCS bucket: `{PROJECT_ID}-state`
   - Generates `backend.tf` files with correct configuration