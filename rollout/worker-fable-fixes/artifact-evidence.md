# Artifact findings 3 and 4

State: regression-first tests added; implementation follows in the next commit.
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
Both tax-only missing SPM columns and a complete artifact with empty receipt years
reproduced failures before implementation edits. The remaining test outcomes will
be recorded after completion. The missing/malformed receipt, damaged HDF, and
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
