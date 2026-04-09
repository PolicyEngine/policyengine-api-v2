# policyengine-api-simulation

Economic comparison service for PolicyEngine's API stack.

## Where this service sits

- `app-v2` still fetches reports and economy comparisons from `https://api.policyengine.org` (`policyengine-api`, the legacy broker).
- The legacy broker forwards society-wide economy comparison work to this simulation service.
- In production, the gateway routes requests to a versioned Modal app built from [src/modal/app.py](./src/modal/app.py).

That means changes to report-output payloads can require coordinated work across three repos:

1. `policyengine.py` for the underlying calculation output
2. `policyengine-api-v2` for the simulation runtime pin and deployment
3. `policyengine-api` and/or `policyengine-app-v2` for cache and UI handling

## `policyengine` version policy

This service intentionally tracks the `policyengine` `0.x` maintenance line.

- Do not bump to `1+` just because the main `policyengine.py` repo has newer releases.
- The legacy broker and report/economy contracts still depend on the pre-`1.0` API surface.
- A `1+` migration needs an explicit compatibility plan across `policyengine-api`, integration tests, and production rollout.

## Source of truth for the `policyengine` pin

[pyproject.toml](./pyproject.toml) is the source of truth for the pinned `policyengine` version.

- [src/modal/policyengine_dependency.py](./src/modal/policyengine_dependency.py) reads that pin for Modal image builds.
- [tests/test_policyengine_dependency_source.py](./tests/test_policyengine_dependency_source.py) verifies the helper and Modal app stay aligned with `pyproject.toml`.

If you need to bump `policyengine`, update the dependency in `pyproject.toml`, then run the checks below.

## Local checks

```bash
uv run pytest tests/test_policyengine_dependency_source.py
uv run pytest
docker build -f projects/policyengine-api-simulation/Dockerfile .
```

Deploy the simulation service with:

```bash
modal deploy src/modal/app.py
```
