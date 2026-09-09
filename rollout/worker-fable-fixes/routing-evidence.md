# Gateway routing and selection evidence

State: Fable finding 1 and the related shared-app, malformed-capability, and partial-selection notes are fixed. Regression tests were committed as `1d6a6ed`; production fixes and expanded rejection coverage were committed as `0bf61df`. The latter includes the runtime agent's narrow `SPM_SCENARIO_UNAVAILABLE` shared error-code addition.

Done:

- Read the exact reviewer output at `/Users/maxghenis/chief-of-staff/state/subfleet/gates/20260909-170551-pr-abdf4629/rounds/001-4542bf03eca1/peer-output.md`, repository testing/PR skills, and the actual `build_legacy_seed_routing_state` producer.
- Route resolution now carries internal provenance for the original country dictionary and `generation="legacy-seed"`. A missing wrapper version permits an ordinary no-SPM request only with this provenance and a numeric US model version at or before the already recognized historical `1.764.6` model. Missing provenance, unknown or later model metadata, future wrapper versions, and every explicit SPM selection fail closed. The classification is not a public request field.
- Annual and budget-window submission tests cover real supported registry shapes, explicit and latest country-version routing, missing wrapper versions, rejection without spawning, and unknown routes. Legacy-dictionary tests use `legacy-app`, for which wrapper-version inference is impossible.
- A shared app resolves a country-model request only when one bundle's country metadata matches and every sibling has enough country metadata to exclude it. Multiple matches or missing sibling model metadata require an explicit `policyengine_version`; latest aliases are excluded from exact-version candidates.
- Malformed stored capabilities are omitted from `/versions` with a warning. Submission against them returns typed `SPM_CONFIGURATION_UNAVAILABLE`, including otherwise historical bundles; no valid-looking capability or worker submission is produced. Tests cover missing pinned hash, unknown contract, extra fields, and incomplete metro defaults.
- Partial geography options are validated together after bundle defaults resolve. A geography-ID-only request can inherit metro defaults, an explicit metro can inherit its existing area, and incompatible county/national defaults still fail. Changing from metro to national clears the area.

Regression-first commands (executed before production edits):

```sh
# cwd: projects/policyengine-simulation-gateway
UV_CACHE_DIR=/tmp/worker-fable-uv-cache UV_PROJECT_ENVIRONMENT=../policyengine-simulation-executor/.venv PYTHONPATH=src:../../libs/policyengine-simulation-contract/src:../../libs/policyengine-simulation-observability/src:../../libs/policyengine-fastapi/src uv run --no-sync python -m pytest tests/test_spm_routes.py -q
# 13 failed, 16 passed: historical submissions, sibling capability selection,
# ambiguous shared-app selection, and malformed capability listing reproduced.

# cwd: libs/policyengine-simulation-contract
UV_CACHE_DIR=/tmp/worker-fable-uv-cache UV_PROJECT_ENVIRONMENT=../../projects/policyengine-simulation-executor/.venv PYTHONPATH=src:../policyengine-simulation-observability/src uv run --no-sync python -m pytest tests/test_spm_selection.py -q
# 2 failed, 3 passed: geography-ID-only and metro-only inheritance reproduced.
```

Verification commands after fixes:

```sh
# cwd: projects/policyengine-simulation-gateway
UV_CACHE_DIR=/tmp/worker-fable-uv-cache UV_PROJECT_ENVIRONMENT=../policyengine-simulation-executor/.venv PYTHONPATH=src:../../libs/policyengine-simulation-contract/src:../../libs/policyengine-simulation-observability/src:../../libs/policyengine-fastapi/src uv run --no-sync python -m pytest tests/test_endpoints.py tests/test_spm_routes.py -q
# 88 passed in 0.53 seconds.

UV_CACHE_DIR=/tmp/worker-fable-uv-cache UV_PROJECT_ENVIRONMENT=../policyengine-simulation-executor/.venv PYTHONPATH=src:../../libs/policyengine-simulation-contract/src:../../libs/policyengine-simulation-observability/src:../../libs/policyengine-fastapi/src uv run --no-sync python -m pytest tests/ -q
# Initial full run: 138 passed, 1 deselected, 1 failed in 0.57 seconds.
# The checked-in OpenAPI golden omitted all pre-existing canonical SPM schemas.
# Root is updating that pre-existing stale golden and rerunning the full suite.

# cwd: libs/policyengine-simulation-contract
UV_CACHE_DIR=/tmp/worker-fable-uv-cache UV_PROJECT_ENVIRONMENT=../../projects/policyengine-simulation-executor/.venv PYTHONPATH=src:../policyengine-simulation-observability/src uv run --no-sync python -m pytest tests/ -q
# 73 passed in 0.04 seconds.

# cwd: repository root
ruff format --check projects/policyengine-simulation-gateway/src/policyengine_simulation_gateway/endpoints.py projects/policyengine-simulation-gateway/tests/test_spm_routes.py libs/policyengine-simulation-contract/src/policyengine_simulation_contract/spm.py libs/policyengine-simulation-contract/tests/test_spm_selection.py
ruff check projects/policyengine-simulation-gateway/src/policyengine_simulation_gateway/endpoints.py projects/policyengine-simulation-gateway/tests/test_spm_routes.py libs/policyengine-simulation-contract/src/policyengine_simulation_contract/spm.py libs/policyengine-simulation-contract/tests/test_spm_selection.py
git diff --check
# All pass.
```

The installed worker environment is Python 3.13.9; source overlays load the owned gateway/contract code. All gateway network/Modal seams are mocked. Native calculator verification belongs to the integrated qualification owned by root and the runtime agent.

Schema equivalence was checked by loading the original contract source with `git show dcfe4fd89d97145882cb147a9aa2ffae2cd10ebf:libs/policyengine-simulation-contract/src/policyengine_simulation_contract/spm.py` into a separate Python module and comparing `model_json_schema()` for `SPMSelection`, `SPMCapability`, `SPMErrorDetail`, `SPMProvenance`, and `SPMComparisonProvenance`. All five are byte-structure equivalent; these routing/validation changes do not introduce a new public schema.

Residual rollout constraint: routine unmeasured future bundles remain unavailable for default US requests. In particular, a newer model without certified `measurements.spm` does not inherit the historical allowance merely because its wrapper is 5.2.0 or 5.3.0. Incomplete route provenance likewise remains unavailable until its metadata is resolved explicitly. No live routes or deployment state were modified.

Next: root completes integrated checks, authenticated native qualification, final source binding/report, and the existing canonical draft PR update. This subtask performed no push, publication, population job, deployment, merge, or changes to untracked root handoffs.

Adversarial follow-up: regression commit `9d16eff` reproduced eight additional failures (37 passing cases) with `tests/test_spm_routes.py -q --tb=no` under the same gateway command environment. A seed could omit the wrapper route that the actual seed producer would infer from a future `policyengine-simulation-py99-0-0` app; an absent/unsupported seed schema was also accepted. Blank sibling model metadata incorrectly excluded that sibling. Fix `2ee006d` requires the supported seed schema, infers the app's wrapper version only when no exact registry candidate exists, and treats blank sibling models as unclassified. Exact registry versions still take precedence over app-name inference.

After the follow-up, the gateway command with `tests/test_spm_routes.py tests/test_endpoints.py -q` passed **98 tests in 0.71 seconds**. Ruff format/check and `git diff --check` passed. Additional direct gateway-helper probes confirmed that a future bundle with each of `spm=None`, `False`, `0`, `[]`, a string, or `{}` raises `SPM_CONFIGURATION_UNAVAILABLE`; none produces an accepted submission. Native runtime changes were independently reviewed against the installed `PolicyEngineSPMProvider`: no actionable typed year/scenario or laziness defect was found, and prevalidation receipts remain private to the discarded provider.
