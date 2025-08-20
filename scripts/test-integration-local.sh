#!/bin/bash
# Script to run integration tests against local docker-compose services

set -e

echo "Starting services with docker-compose..."
docker-compose -f deployment/docker-compose.yml up -d

echo "Waiting for services to be ready..."
# Wait for services to start up
sleep 5

# Function to check if a service is responding
check_service() {
    local SERVICE_NAME=$1
    local PORT=$2
    local MAX_ATTEMPTS=30
    local ATTEMPT=0
    
    echo -n "Checking $SERVICE_NAME on port $PORT..."
    while [ $ATTEMPT -lt $MAX_ATTEMPTS ]; do
        if curl -s -o /dev/null -w "%{http_code}" "http://localhost:$PORT/ping/alive" | grep -q "200"; then
            echo " ✅ Ready!"
            return 0
        fi
        ATTEMPT=$((ATTEMPT + 1))
        echo -n "."
        sleep 2
    done
    echo " ❌ Failed to connect after $MAX_ATTEMPTS attempts"
    return 1
}

# Check each service
check_service "api-full" 8081
check_service "api-simulation" 8082
check_service "api-tagger" 8083

echo ""
echo "Running integration tests..."
make test-integration

echo ""
echo "Stopping services..."
docker-compose -f deployment/docker-compose.yml down

echo "✅ Integration tests completed!"