# Deployment guide

## Prerequisites

- GCP project with billing enabled
- `gcloud` CLI installed and authenticated
- Docker installed
- Terraform 1.5+ installed

## Setup

1. Copy and configure environment:
```bash
cp deployment/.env.example deployment/.env
# Edit deployment/.env with your project details
```

2. For existing GCP projects with resources:
```bash
# If you get "already exists" errors, run:
make terraform-import

# For workflow errors specifically (workflows can't be imported):
./deployment/terraform/handle-existing-workflows.sh $PROJECT_ID
# To auto-delete existing workflows, add --delete flag:
# ./deployment/terraform/handle-existing-workflows.sh $PROJECT_ID us-central1 --delete
```

3. Deploy:
```bash
make deploy
```

## How it works

- **Terraform state**: Stored in GCS bucket `{PROJECT_ID}-state`
- **Auto-populated variables**: Commit URL and package versions are extracted automatically
- **Shared state**: Works across multiple machines via GCS backend

## Troubleshooting

### Resources already exist errors

If you see errors about resources already existing:

1. Run `make terraform-import` to import existing resources
2. Then run `make deploy` again

### Starting fresh

To destroy all terraform-managed resources:

```bash
make terraform-destroy
```

Then you can deploy fresh with `make deploy`.