# PR677 Fable fixes

All four findings are fixed locally. The final combined qualification passed **34 installed native tests, zero skips or failures**, in 288.39 seconds. Service/client checks complete **747 passes** (including the explicitly retested version-extraction case). Remote delivery is blocked by this session's access restrictions, not by a code or test failure.

## Source and review binding

- Owned checkout: `/Users/maxghenis/spm-rebuild-20260908/worktrees/policyengine-sim-api-canonical`.
- Starting worker head: `dcfe4fd89d97145882cb147a9aa2ffae2cd10ebf`.
- Final implementation and tests: `c431d138bdbad9be71c12b6994851879cf5d05aa`; later commits contain qualification evidence and reports only.
- Live canonical `main`: `414c631d622f5f587eedd187296a80182a923db2`, independently fetched through the authenticated GitHub connector and equal to local `origin/main`. No base integration or checkout was needed.
- Existing issue: [#676](https://github.com/PolicyEngine/policyengine-sim-api/issues/676), verified open and appropriate. Existing [PR677](https://github.com/PolicyEngine/policyengine-sim-api/pull/677) is draft, unmerged, on canonical branch `max/spm-simulation-canonical-20260909`, still remotely at the starting head.
- Exact reviewer output read: `/Users/maxghenis/chief-of-staff/state/subfleet/gates/20260909-170551-pr-abdf4629/rounds/001-4542bf03eca1/peer-output.md`. Its complete findings remain valid despite dispatch's BrokenPipeError. **No durable Fable agreement exists or is claimed.**
- Repository testing/PR skills, installed PolicyEngine analysis/standards/API skills, parent PolicyEngine guidance, and wrapper repository guidance were read. GitNexus debugging guidance was read; no callable GitNexus graph was available, so source tracing used the actual repository and installed packages.
- Untracked root `PROGRESS.md` and `WORKER-CANONICAL-SPM-HANDOFF.md` were preserved. Their original fingerprints are committed in `handoff-preservation.json`. This continuation's committed state/done/next journal is the adjacent `PROGRESS.md`.

## Finding disposition

| Finding | Disposition and concrete proof |
| --- | --- |
| 1. Historical routes without wrapper versions incorrectly return 400 | Fixed. Internal route provenance distinguishes the actual legacy country dictionary and schema-v1 `legacy-seed` paths. Unknown-wrapper acceptance additionally requires a numeric historical US model through 1.764.6. A future wrapper inferable from the app name cannot be erased by missing seed metadata. Annual and budget-window submissions accept supported historical shapes; explicit SPM selections, future/unknown models, unproven seeds, ambiguous siblings and malformed capabilities reject. |
| 2. Year/scenario prevalidation loses typed errors | Fixed. Uses the installed `PolicyEngineSPMProvider.year_metadata` contract, preserving `SPM_YEAR_UNAVAILABLE` at annual/year-alias and budget-window start/end boundaries. Narrow scenario translation matches the calculator's public adapter contract and preserves `SPM_SCENARIO_UNAVAILABLE` through HTTP/poll/pickle/optional-analysis transport. Other invalid settings retain `SPM_SETTINGS_INVALID`. Prevalidation does not measure amounts; actual country tax-only calculations remain lazy outside forecast years. |
| 3. Incomplete cached receipt becomes fatal | Fixed. Check required columns first; an unusable cached receipt follows incomplete → run/save/cache replacement. Capture the requested selection before wrapper cache restoration and restore it before recomputation. Eight real one-household HDF/cache cases cover tax-only missing columns, empty years, missing/malformed receipt, changed recorded selection, corrupt HDF and cache selection isolation; repaired disk and memory results replay as valid hits. Real run/save errors still propagate. |
| 4. Precompute omits storage identity check | Fixed. Compare actual wrapper `storage_id` with `Path(expected.path).stem`, the planner's serialized storage identity, beside the existing simulation-id guard and before configuring, running or uploading. Historical wrappers without the property retain their bare-id contract. A mismatch rejects even when simulation ids agree; the installed-wrapper identity test passes. |

Related notes are also resolved: shared-app routing uses exact country metadata only when every sibling is positively classified, excludes `latest` aliases, and rejects missing/blank metadata or unresolved ambiguity. Invalid stored capabilities are omitted with a warning from `/versions` and rejected with a typed configuration error on submission. Coupled geography validation happens after defaults resolve, so partial metro area selections obey the declared inheritance contract while invalid resolved combinations fail. Public SPM schemas remain unchanged by those validation fixes. The stale gateway golden from the original PR was regenerated, and entry/gateway schema comparison now covers their shared SPM schema instead of stripping it.

The runtime-capability performance note was intentionally left alone. No performance refactor or unrelated model/style change was made. See `routing-evidence.md`, `runtime-evidence.md`, and `artifact-evidence.md` for detailed regression-first evidence and bounded independent cross-reviews.

## Checks and exact commands

Commands below were run in this checkout, with service commands run from the stated directory. `WORKER`, `QUAL`, `PY`, and `OUT` expand as follows:

```sh
WORKER=/Users/maxghenis/spm-rebuild-20260908/worktrees/policyengine-sim-api-canonical
QUAL=/Users/maxghenis/spm-rebuild-20260908/rollout/year-boundary-qualification
PY="$WORKER/projects/policyengine-simulation-executor/.venv/bin/python"
OUT="$WORKER/rollout/worker-fable-fixes"
```

| Check | Result |
| --- | --- |
| Gateway full unit suite | 149 passed, 1 integration case deselected; 0.77 seconds. |
| Entry full unit suite | 66 passed; 1.20 seconds. |
| Shared contract full suite | 73 passed; 0.05 seconds. |
| Executor full suite | 454 passed, 22 opt-in native cases skipped, 2 integration cases deselected; one dependency-download failure, 23.62 seconds. That exact version-extraction test passed with syncing disabled, 1.21 seconds, completing 455 unit checks. |
| Actual regenerated Python client | 4 passed; 0.13 seconds. |
| Installed native/runtime regression lane | Clean RED: 8 failures / 3 passes. GREEN: 56 canonical/runtime checks passed, zero skips. |
| Installed artifact/precompute lane | Clean RED: 6 failures / 40 passes (five target defects plus an existing bare-id filename assertion). GREEN: 45 passed plus the separately corrected identity assertion passed; all 8 actual native artifact cases passed. |
| Combined authenticated native qualification | **34 passed, zero skipped/failed**, 2 expected plugin-rewrite warnings; 288.39 seconds. Covers original native bridge, prior lazy tax-only/provider behavior, all 8 artifact cases and 11 new runtime boundary cases. |
| Installed dependency check | All 180 distributions compatible. |
| Ruff format/lint and diff whitespace | All 16 changed Python files pass; `git diff --check` passes. |
| Pyright against exact installed environment | Entry/contract: zero diagnostics. Executor: 145; gateway: 78. Counts and diagnostic identities exactly match the archived unchanged starting source, with **zero new diagnostics**. |

Full service commands, from the corresponding gateway, entry, executor, or shared-contract project directory:

```sh
env -u PYTHONPATH UV_CACHE_DIR=/tmp/worker-fable-uv-cache \
  uv run --offline --no-project --python "$PY" python -m pytest tests/ -q
```

The executor's pre-existing script test calls `uv run` internally, which attempted an unavailable NumPy download. It was rerun against the existing installed environment without synchronization:

```sh
# cwd: projects/policyengine-simulation-executor
env -u PYTHONPATH UV_CACHE_DIR=/tmp/worker-fable-uv-cache UV_NO_SYNC=1 \
  uv run --offline --no-project --python "$PY" python -m pytest \
  tests/test_modal_scripts.py::TestModalExtractVersions::test_extracts_versions_from_policyengine_bundle -q
```

Client generation and actual generated-client checks:

```sh
# cwd: checkout root
UV_CACHE_DIR=/tmp/worker-fable-uv-cache UV_OFFLINE=1 ./scripts/generate-clients.sh
# cwd: projects/policyengine-apis-integ
PYTHONPATH="$WORKER/projects/policyengine-simulation-entry/artifacts/clients/python" \
  UV_CACHE_DIR=/tmp/worker-fable-uv-cache \
  uv run --offline --no-project --python "$PY" python -m pytest \
  tests/test_spm_generated_client.py -q
```

The gateway golden was regenerated with the actual module, then copied from its generated output as documented by the golden test:

```sh
# cwd: projects/policyengine-simulation-gateway
env -u PYTHONPATH UV_CACHE_DIR=/tmp/worker-fable-uv-cache \
  uv run --offline --no-project --python "$PY" python -m policyengine_simulation_gateway.generate_openapi
cp artifacts/openapi.json tests/golden/openapi.json
```

Combined installed qualification, dependency and lint commands, from the checkout root:

```sh
env -u PYTHONPATH PYTHONSAFEPATH=1 UV_CACHE_DIR=/tmp/worker-fable-uv-cache \
  uv run --offline --no-project --python "$QUAL/venv/bin/python" \
  python -P rollout/worker-fable-fixes/run_installed_qualification.py
UV_CACHE_DIR=/tmp/worker-fable-uv-cache uv pip check --python "$QUAL/venv/bin/python"
git diff --name-only dcfe4fd HEAD -- '*.py' > "$OUT/changed-python-files.txt"
UV_CACHE_DIR=/tmp/worker-fable-uv-cache uv run --offline --no-project ruff format --check $(cat "$OUT/changed-python-files.txt")
UV_CACHE_DIR=/tmp/worker-fable-uv-cache uv run --offline --no-project ruff check $(cat "$OUT/changed-python-files.txt")
git diff --check
```

Pyright used the installed cached 1.1.411 distribution, with identical Python 3.13 settings, source overlays and authenticated qualification venv on both sides. The base was created with `git archive dcfe4fd89d97145882cb147a9aa2ffae2cd10ebf | tar -x -C /tmp/worker-fable-base`, without a checkout. Each of the executor/gateway `base` and `current`, plus current entry/contract checks used:

```sh
node /Users/maxghenis/.cache/uv/archive-v0/ELraG5tqAzXmiwNiWpYsc/pyright/dist/index.js \
  --project "$OUT/current-executor-pyrightconfig.json" --outputjson
```

Replace the config basename with `base-executor`, `base-gateway`, `current-gateway`, `current-entry` or `current-contract` as appropriate. The exact configurations and raw diagnostic JSON remain locally in this evidence directory; the diagnostic comparison is committed as `typing-comparison.json`. Bulk service/native logs are retained locally but ignored by git; selected runtime regression outputs are committed. Regression-first commands and outcomes are in the three committed lane evidence files.

## Authenticated scientific inputs and qualification limits

| Package | Version | Wheel SHA256 |
| --- | --- | --- |
| policyengine | 5.3.0 | `8c640d967575dddad70840bcbe938cea251c56958eded647c83eb9c5902735f1` |
| policyengine-us | 1.824.7 | `7644819916a4f8ca2aa37a4a9d992fa834bfa66ab2d441326a9686baa5c1a688` |
| policyengine-core | 3.30.1 | `2dbcf5f590a0199a7b7c77fcbbda2ff6bc289f6c6169ca0af3beace35d8b3e63` |
| spm-calculator | 1.0.0 | `c49c41da5fd482e563eaea956e205a3ba6841cadd4dd32bef4c0c3dbce17ffba` |

The harness checks all 17,613 installed scientific package files byte for byte against these wheels and checks real import origins. Only worker/shared-library source is overlaid. It reuses the existing reviewed development manifest and explicit bootstrap; it does not fabricate receipt/version metadata or certify the inherited data. Actual artifact receipts are produced by the installed model/calculator, then deliberately damaged only within temporary regression fixtures. The model source itself is unchanged. `native-wheel-summary.json` records all 34 passing cases, import origins and the raw authenticated receipt digest; `source-binding.json` binds all 190 tracked worker/source test files byte for byte to the implementation commit. Post-run checks confirm those files and both untracked handoffs are unchanged.

Forecast content identity: `3d86d5c4c0423480e6b69b75d222ffa4a7a2639e4094df5ba2504af01be17173`. Native H5 identity: `6496cc4393d4d3c6574f76eca231de5898c803b9067645591fd5c4d3e65aee84`; only its indexed first household and four people are simulated, and its full hash is checked before and after. The existing explicit development manifest is SHA256 `c78faac072f85109ac50d36a9e538a4dae56af4cdc98d2281603a3f4849a591f`; the bootstrap is SHA256 `f762892a374c3950af54834f0fb234708addc59ad4af90aab99866eb37e27a5e`.

Earlier temporary launchers exposed an unrelated pre-existing `/private/tmp/h2.py` through Python's script-directory import path; that file printed another experiment's output. Those runs were discarded/interrupted and superseded by clean safe-path runs. The unrelated file was not modified. The qualification command clears inherited `PYTHONPATH` and uses explicit installed Python 3.13; the final harness requires the variable to be absent and rejects `/tmp` on `sys.path`.

Residual risks: no durable Fable agreement; existing executor/gateway type debt remains; final published model/data bundle, required CI, Docker/service integration and live rollout verification remain outside this bounded local qualification. Unknown future legacy bundles still need explicit measured capability or a reviewed routing/model contract; absence of capability never broadly implies legacy. Scenario error translation remains coupled to the calculator adapters' narrow, tested message prefix. No browser, population job, package/data publication, deployment, merge, external messaging, `.err` read or `.lane.log` read occurred.

## Delivery status

Local coherent steps are committed throughout. `git fetch origin`, `gh repo view`, and `git push origin HEAD:refs/heads/max/spm-simulation-canonical-20260909` failed on GitHub DNS/API connectivity. Authenticated connector reads confirmed the canonical repository, base, issue and draft PR. The fallback GitHub write tool returned: **“MCP tool call requires approval, but approval policy is never.”** No remote Git object, branch or PR-body mutation occurred; the API transfer was stopped at that boundary.

The reviewed, update-ready body is `PR-BODY.md`, beginning `Fixes #676`. It is prepared locally and has not been posted. Per `docs/engineering/skills/github-prs.md`, “If you cannot push to the canonical repository, stop and ask for access. Do not create a fork PR as a fallback.” Finishing delivery requires Git network access or an approved GitHub write channel; no fork fallback or merge is authorized or attempted.
