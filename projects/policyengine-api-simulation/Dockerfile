FROM python:3.13

# Install uv
RUN pip install uv

WORKDIR /app

# Copy the entire project structure for dependencies
COPY libs/policyengine-fastapi ./libs/policyengine-fastapi/
COPY projects/policyengine-api-simulation ./projects/policyengine-api-simulation/

WORKDIR /app/projects/policyengine-api-simulation

# Install dependencies using uv
RUN uv sync --frozen --no-dev

EXPOSE 8080

# Run with uv - using 2 workers (one for requests, one for liveness check)
CMD ["uv", "run", "uvicorn", "src.policyengine_api_simulation.main:app", "--host", "0.0.0.0", "--port", "8080", "--workers", "2"]