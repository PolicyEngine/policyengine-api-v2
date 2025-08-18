FROM python:3.13-slim
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Set environment variables
ENV ENVIRONMENT="production" \
    JWT_ISSUER=https://your_production_issuer/ \
    JWT_AUDIENCE=https://your_production_api/ \
    OT_SERVICE_NAME=policyengine_full_api \
    OT_SERVICE_INSTANCE_ID=instance

WORKDIR /app

# Copy LICENSE file to the root where it's expected
COPY LICENSE ./LICENSE

# Copy the entire project structure for dependencies
COPY libs/policyengine-fastapi ./libs/policyengine-fastapi/
COPY projects/policyengine-api-full ./projects/policyengine-api-full/

WORKDIR /app/projects/policyengine-api-full

# Install dependencies using uv
RUN uv sync --frozen --no-dev

EXPOSE 8080

# Run with uvicorn
CMD ["uv", "run", "uvicorn", "policyengine_api_full.main:app", "--host", "0.0.0.0", "--port", "8080"]