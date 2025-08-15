FROM python:3.13-slim

# Install uv
RUN pip install uv

# Set environment variables
ENV ENVIRONMENT="production" \
    OT_SERVICE_NAME=policyengine_tagger_api \
    OT_SERVICE_INSTANCE_ID=instance

WORKDIR /app

# Copy the entire project structure for dependencies
COPY libs/policyengine-fastapi ./libs/policyengine-fastapi/
COPY projects/policyengine-api-tagger ./projects/policyengine-api-tagger/

WORKDIR /app/projects/policyengine-api-tagger

# Install dependencies using uv
RUN uv sync --frozen --no-dev

EXPOSE 8080

# Run with uv
CMD ["uv", "run", "fastapi", "run", "src/policyengine_api_tagger/main.py", "--port", "8080"]