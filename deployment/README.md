# Deployment configuration

This directory contains all deployment-related files:

- `docker-compose.yml` - Local development environment
- `docker-compose.prod.yml` - Production build configuration
- `.env.example` - Example environment variables
- `cloudbuild.yaml` - GCP Cloud Build configuration

## Quick start

```bash
# Copy environment variables
cp deployment/.env.example deployment/.env

# Start local development
make dev

# Build production images
make build-prod

# Deploy to GCP
make deploy
```