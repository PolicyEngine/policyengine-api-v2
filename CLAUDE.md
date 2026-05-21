# PolicyEngine API v2

FastAPI and Modal-based API infrastructure for PolicyEngine services.

Claude and other AI coding agents should follow the repository guidance in
`AGENTS.md`. In particular:

- open an issue before non-trivial PRs,
- open same-repository draft PRs by default,
- start each draft PR description with `Fixes #ISSUE_NUMBER`,
- run formatting and relevant tests before opening the PR.

## Common Commands

```bash
make format
make check
make test
make test-complete
./scripts/generate-clients.sh
```

For simulation-service-only work:

```bash
cd projects/policyengine-api-simulation
uv sync --extra test
uv run pytest tests/ -v
```

## Key Paths

- `projects/policyengine-api-simulation/` — simulation gateway and Modal worker
- `projects/policyengine-apis-integ/` — generated-client integration tests
- `libs/policyengine-fastapi/` — shared FastAPI utilities
- `.github/workflows/pr.yml` — PR checks
- `.github/workflows/modal-deploy.yml` — main-branch Modal deployment
