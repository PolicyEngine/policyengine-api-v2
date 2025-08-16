FROM python:3.13

# Install uv
RUN pip install uv

# Set environment variables
ENV ENVIRONMENT="desktop" \
    OT_SERVICE_NAME=policyengine_household_api \
    OT_SERVICE_INSTANCE_ID=instance

WORKDIR /app

# Copy LICENSE file to the root where it's expected
COPY LICENSE ./LICENSE

# Copy the entire project structure for dependencies
COPY libs/policyengine-api ./libs/policyengine-api/
COPY projects/policyengine-household-api ./projects/policyengine-household-api/

WORKDIR /app/projects/policyengine-household-api

# Install dependencies using uv
RUN uv sync --frozen --no-dev

EXPOSE 8080

# Run with uvicorn - add src to PYTHONPATH and run
ENV PYTHONPATH=/app/projects/policyengine-household-api/src
CMD ["uv", "run", "uvicorn", "policyengine_household_api.main:app", "--host", "0.0.0.0", "--port", "8080"]