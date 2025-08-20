#!/bin/bash
# Script to generate OpenAPI specs and Python client libraries

set -e

echo "Generating OpenAPI specs and client libraries..."

# Function to generate client for a service
generate_client() {
    local SERVICE=$1
    local PROJECT_DIR="projects/policyengine-api-${SERVICE}"
    
    echo "Processing ${SERVICE} API..."
    
    # Generate OpenAPI spec
    echo "  Generating OpenAPI spec..."
    cd "${PROJECT_DIR}"
    
    # Install build dependencies if not already installed
    uv sync --extra build
    
    uv run python -m policyengine_api_${SERVICE//-/_}.generate_openapi
    
    # Check if OpenAPI spec was created
    if [ ! -f "artifacts/openapi.json" ]; then
        echo "  ❌ Failed to generate OpenAPI spec for ${SERVICE}"
        return 1
    fi
    
    # Generate Python client
    echo "  Generating Python client..."
    mkdir -p artifacts/clients
    uv run openapi-python-client generate \
        --path artifacts/openapi.json \
        --output-path artifacts/clients/python \
        --overwrite
    
    # Update client package name
    if [ -f "artifacts/clients/python/pyproject.toml" ]; then
        sed -i.bak "s/^name = .*/name = \"policyengine_api_${SERVICE//-/_}_client\"/" artifacts/clients/python/pyproject.toml
        rm artifacts/clients/python/pyproject.toml.bak
    fi
    
    echo "  ✅ Client generated for ${SERVICE}"
    cd ../..
}

# Generate clients for both services
generate_client "full"
generate_client "simulation"

echo "✅ All clients generated successfully!"
echo ""
echo "To use the clients in integration tests, run:"
echo "  cd projects/policyengine-apis-integ"
echo "  uv sync"