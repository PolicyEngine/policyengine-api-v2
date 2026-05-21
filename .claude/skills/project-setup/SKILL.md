---
name: Project Setup
description: >
  Use when the user asks about local development setup, installing
  dependencies, running tests, generating clients, deploying, or understanding
  the PolicyEngine API v2 repository layout.
version: 0.1.0
---

# Project Setup

PolicyEngine API v2 is a monorepo with service projects, shared libraries, and
deployment configuration.

## Common Commands

```bash
make setup
make up
make logs
make down
make format
make check
make test
make test-complete
./scripts/generate-clients.sh
```

## Service-Scoped Simulation Commands

```bash
cd projects/policyengine-api-simulation
uv sync --extra test
uv run pytest tests/ -v
```

## Project Layout

| Path | Purpose |
| ---- | ------- |
| `projects/policyengine-api-simulation/` | Simulation API gateway and Modal worker |
| `projects/policyengine-apis-integ/` | Generated-client integration tests |
| `libs/policyengine-fastapi/` | Shared FastAPI utilities |
| `deployment/` | Docker Compose and Terraform deployment configuration |
| `.github/workflows/pr.yml` | Pull request checks |
| `.github/workflows/modal-deploy.yml` | Main-branch Modal deployment |

## PR Preparation

Before opening a PR, read `.claude/skills/github-prs.md` and `AGENTS.md`.
