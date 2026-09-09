# Artifact findings 3 and 4

State: findings 3 and 4 fixed; regression-first and installed qualification passed.
The exact Fable review from gate `20260909-170551-pr-abdf4629`, round
`001-4542bf03eca1`, was read along with the repository testing skill. No durable
agreement is inferred from that review.

The installed regression harness authenticates the original c49c calculator,
76448 country, 8c640 wrapper and 2dbc core wheels with the existing qualification
script's complete verification/bootstrap prefix. It uses the original explicit
unverified development manifest; it does not synthesize receipt/version metadata.
Tests calculate authentic one-household receipts and deliberately damage only
local temporary artifacts or cache entries when exercising corruption handling.

Clean regression command (worker repository root):

```sh
env -u PYTHONPATH UV_CACHE_DIR=/private/tmp/worker-fable-uv-cache \
  uv run --no-project \
  --python /Users/maxghenis/spm-rebuild-20260908/rollout/year-boundary-qualification/venv/bin/python \
  python -P rollout/worker-fable-fixes/run_artifact_native.py \
  projects/policyengine-simulation-executor/tests/test_baseline_artifacts_spm_native.py \
  projects/policyengine-simulation-executor/tests/test_precompute.py \
  -q -p no:cacheprovider --basetemp /private/tmp/worker-fable-artifact-red-clean \
  > rollout/worker-fable-fixes/artifact-native-red-clean.log 2>&1
```

The clean run imports the unchanged artifact implementations from `dcfe4fd`.
The clean RED run completed with **6 failed, 40 passed in 173.47 seconds**. Five
failures reproduce the target defects: tax-only missing columns, complete columns
with empty receipt years, cached missing receipt, cached sibling selection, and
planned storage-id mismatch. A sixth, previously existing test assertion assumed
all planned filenames were bare simulation ids; it now asserts the planner
`storage_id`, which preserves the legacy contract and handles actual SPM bundles. The missing/malformed receipt, damaged HDF, and
recorded-selection isolation cases exercise the actual installed wrapper load,
save, cache, and model calculation paths. A focused precompute test expects
rejection when simulation ids agree but the planned storage filename differs.

An earlier attempt used `/private/tmp/run_artifact_native.py`; the script directory
made unrelated `/private/tmp/h2.py` shadow an optional dependency, so that run was
interrupted and is superseded. The repository-owned launcher plus `python -P`
removes that import path; its clean output has none of the unrelated experiment
text. An initial bare `uv run --no-sync pytest` selected an inherited Python 3.14
executable and failed collection; it provides no test evidence. All qualification
commands now select the authenticated Python 3.13 environment explicitly.

Ruff check passes for the four new/updated test files after formatting. Root
handoff files were left untouched.


## Final implementation and checks

The guard captures the original request selection before the installed wrapper
restores cached metadata. Missing columns are checked before receipt validation;
invalid cached receipts take `OUTCOME_INCOMPLETE` and the existing run/save/cache
replacement path. The request selection is restored before recompute. Real run or
save errors still propagate. Missing/malformed HDF receipts, differing recorded
selections, and corrupt HDF bytes retain the wrapper's existing miss/recompute
behavior. The repaired artifacts and cache entries then replay as hits with valid
actual calculation receipts and without another model run.

Precompute compares the real wrapper's `storage_id` (falling back to id only for
historical wrappers) with `Path(expected.path).stem`, which is the planner's
serialized storage id. This occurs beside the simulation-id comparison, before
configuration, ensure, or upload. No precompute wire schema changed.

Final GREEN used the clean command above with
`--basetemp /private/tmp/worker-fable-artifact-green` and
`-k 'not test_precompute_identity_equals_runtime_id'`, writing
`artifact-native-green.log`: **45 passed, 1 deselected, 2 warnings in 207.33 seconds**.
All eight native artifact cases passed. The deselected assertion had been
corrected separately after the GREEN process imported its test module; the
following exact installed check closes that case: **1 passed, 2 warnings in
0.09 seconds** (`artifact-installed-identity.log`).

```sh
env -u PYTHONPATH UV_CACHE_DIR=/private/tmp/worker-fable-uv-cache \
  uv run --no-project \
  --python /Users/maxghenis/spm-rebuild-20260908/rollout/year-boundary-qualification/venv/bin/python \
  python -P rollout/worker-fable-fixes/run_artifact_native.py \
  projects/policyengine-simulation-executor/tests/test_precompute.py::TestWriterReaderContract::test_precompute_identity_equals_runtime_id \
  -q -p no:cacheprovider --basetemp /private/tmp/worker-fable-artifact-identity \
  > rollout/worker-fable-fixes/artifact-installed-identity.log 2>&1
```

From `projects/policyengine-simulation-executor`, the explicit historical Python
3.13 focused suite also passed **68 tests in 13.02 seconds**:

```sh
env -u PYTHONPATH UV_CACHE_DIR=/private/tmp/worker-fable-uv-cache \
  uv run --no-sync --python .venv/bin/python .venv/bin/python -m pytest \
  tests/test_baseline_artifacts.py tests/test_precompute.py -q
```

After the storage filename assertion correction, repeating just
`tests/test_precompute.py -q` with the same command prefix passed **38 tests in
0.88 seconds**. Ruff check and format-check pass for both source files, all four
artifact/native test/helper files, and the launcher (seven Python files total).
The executor test venv lacks the `pyright` module; the coordinator's established
full typecheck covers both changed source files and reports the same 145
pre-existing executor diagnostics as `dcfe4fd`, with zero new diagnostics.

The runtime-errors agent independently reviewed the artifact/precompute diff
against the installed wrapper's actual ensure/load/run/cache code and found no
additional actionable safety defect. This is a bounded peer review, not a durable
Fable agreement. No artifact upload, deployment, publication, or population
calculation was performed. Remote cached artifacts were not changed; these fixes
repair a loaded incomplete artifact locally by recomputing.

## Source binding

These final source hashes bind the implementation. GREEN executed identical
Python code before an outcome-comment-only edit. Root's final qualification and
source inventory bind the integrated branch head and all test files.

| Source | SHA256 |
| --- | --- |
| `baseline_artifacts.py` | `2ec0d48bd97bad7a663deaf49b7a12c5b887d6b29f571e2cfe90d3c4247ad9c1` |
| `precompute.py` | `2c2a9bb6c824f4cce603f5728ea4cc58a693f8f354beff10b4cb370d41914e45` |
