# PolicyEngine API v2 Agent Guide

This repository is the PolicyEngine API v2 monorepo. It contains service
projects under `projects/`, shared libraries under `libs/`, deployment
configuration under `deployment/`, and GitHub Actions under `.github/`.

## Development

- Use Python 3.13 and `uv`.
- Prefer repo Makefile targets when they match the task:
  - `make format` formats Python source with Ruff.
  - `make check` runs Ruff and Pyright over source directories.
  - `make test` runs service unit tests in Docker.
  - `make test-complete` runs unit and local integration tests.
- For service-scoped work, run focused `uv run pytest ...` commands from the
  relevant project directory when that is faster and sufficient.
- Regenerate generated clients with `./scripts/generate-clients.sh` when API
  schemas change.

## Pull Requests

- Do not commit directly to `main`.
- For non-trivial work, open a GitHub issue before opening a PR.
- Open same-repository draft PRs by default.
- The first line of every draft PR description must be
  `Fixes #ISSUE_NUMBER`.
- Include concise `Summary` and `Testing` sections after the `Fixes #...`
  line.
- Before opening a PR, run formatting and the most relevant tests for the
  changed surface. If you cannot run expected checks, say so in the PR body.
- Use `gh` for GitHub operations when possible so repository Actions and
  permissions behave consistently.

## Repository Notes

- The simulation service lives in `projects/policyengine-api-simulation`.
- API integration tests live in `projects/policyengine-apis-integ`.
- PR CI runs simulation unit tests, Ruff format checks, Docker build, and local
  integration tests.
- There is currently no repository-wide changelog fragment requirement.
