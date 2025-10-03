# Local development queue system

## Overview

This setup mimics Google Cloud Workflows behaviour for local development. The queue worker script polls the database for pending simulations, aggregates, and aggregate changes, then calls the simulation API to process them.

## Architecture

1. **Full API** (`policyengine-api-full`): Creates simulations/aggregates/aggregate changes in the database without computing them
2. **Queue Worker** (`queue_worker.py`): Polls database for pending items and sends them to the simulation API
3. **Simulation API** (`policyengine-api-simulation`): Processes items synchronously and saves results back to database

## Setup

### 1. Start the database
```bash
# In policyengine.py or wherever Supabase is configured
supabase start
```

### 2. Start the full API
```bash
cd ../policyengine-api-v2/projects/policyengine-api-full
uv run uvicorn policyengine_api_full.main:app --port 8000 --reload
```

### 3. Start the simulation API
```bash
cd ../policyengine-api-v2/projects/policyengine-api-simulation
uv run uvicorn policyengine_api_simulation.main:app --port 8001 --reload
```

### 4. Start the queue worker
```bash
cd ../policyengine-api-v2/projects/policyengine-api-simulation
python queue_worker.py --interval 5 --api-url http://localhost:8001
```

## How it works

### Simulations
- Frontend creates simulation via `POST /simulations/` (full API)
- Simulation is saved to DB with `result = NULL`
- Queue worker finds it and calls `POST /run_simulation_sync/{id}` (simulation API)
- Simulation API runs computation and saves result
- Frontend polls `GET /simulations/{id}` until `result` is not null

### Aggregates
- Frontend creates aggregates via `POST /aggregates/bulk` (full API)
- Aggregates saved to DB with `value = NULL`
- Queue worker finds them and calls `POST /process_aggregates` (simulation API)
- Simulation API runs computations and saves values
- Frontend polls until all `value` fields are not null

### Aggregate changes
- Frontend creates via `POST /aggregate-changes/bulk` (full API)
- Saved to DB with `change = NULL`
- Queue worker calls `POST /process_aggregate_changes` (simulation API)
- Simulation API computes and saves
- Frontend polls until all `change` fields are not null

## Queue worker options

```bash
python queue_worker.py --help
```

Options:
- `--interval SECONDS`: Polling interval (default: 5)
- `--api-url URL`: Simulation API URL (default: http://localhost:8001)
- `--database-url URL`: Database URL (uses DATABASE_URL env var by default)

## Production behaviour

In production, the queue worker is replaced by Google Cloud Workflows, which:
- Triggers on database changes
- Calls the simulation API endpoints
- Handles retries and failures
