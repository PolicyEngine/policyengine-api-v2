# Multi-stage build inheriting from base
# Use explicit platform for consistency across builds
FROM --platform=linux/amd64 python:3.13-slim AS base

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Install git
RUN apt-get update && apt-get install -y git && apt-get clean && rm -rf /var/lib/apt/lists/*

# Set common environment variables
ENV ENVIRONMENT="production"

WORKDIR /app

# Copy shared libraries and LICENSE
COPY LICENSE ./LICENSE
COPY libs ./libs/ 

# Final stage
FROM base AS final

# Service-specific environment
ENV OT_SERVICE_NAME=policyengine_full_api \
    OT_SERVICE_INSTANCE_ID=instance

# Copy service-specific code
COPY projects/policyengine-api-full ./projects/policyengine-api-full/

WORKDIR /app/projects/policyengine-api-full

# Install dependencies
RUN uv sync --frozen --no-dev

EXPOSE 8080

# Install policyengine from the api-v2 branch
RUN uv pip install git+https://github.com/PolicyEngine/policyengine.py@api-v2

# Run with uvicorn
CMD ["uv", "run", "uvicorn", "policyengine_api_full.main:app", "--host", "0.0.0.0", "--port", "8080"]