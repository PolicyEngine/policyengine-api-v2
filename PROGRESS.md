# PR #677 review fixes — progress

Branch: `max/spm-simulation-canonical-fixes-20260911` (from PR head `b0447ca`)
Target PR branch: `max/spm-simulation-canonical-20260909`
Base: `main` = `414c631d622f5f587eedd187296a80182a923db2`

## State

All nine review findings are addressed, and an adversarial re-audit of the
eight already-closed ones found three claims that only held because nothing
tested them; those are closed too (`fd869e7`). Suites green locally.

## Findings checklist

- [x] Medium 1 — completed results drop explicit nulls from `spm_config` on the wire
- [x] Medium 2 — legacy no-SPM provenance `legacy-seed` expires on next publish
- [x] Medium 3 — precompute storage identity never shown to match the wrapper
- [x] Medium 4 — budget-window scheduler typed-error branches untested
- [x] Low 1 — legacy no-SPM poll bodies not byte-identical to base
- [x] Low 2 — stale country routes now fail; undocumented, untested
- [x] Low 3 — segmented reduce with SPM children untested end to end
- [x] Low 4 — hermetic CI never exercises receipt validation in `ensure()`
- [x] Low 5 — repeated prevalidation per request (perf)

## Done

- **Medium 1** (`b074b95`, `bf6764c`): `SPMSelection.serialize_selection`
  keeps options that were explicitly selected as null when the caller
  serializes with `exclude_none` (the poll routes do, via
  `response_model_exclude_none`). Covered at the gateway
  (`test_completed_result_body_keeps_resolved_nulls`,
  `test_completed_budget_window_rows_keep_resolved_nulls`) and at the
  contract layer, where reverting the serializer had left the suite green.
- **Medium 2** (`4992a19`): route provenance is derived from route shape
  (`policyengine_version is None and schema_version == 1` ->
  `legacy-country-route`) instead of the registry's rewritable `generation`
  marker, and `_certified_model_version` stops reading a wrapper version as
  a country model version, so a pinned 5.2.0/5.3.0 route with no manifest
  stays historical.
- **Medium 3** (`ae9489e`, `3b28b9a`, `2b52202`): the planner's storage id
  is held against the wrapper's own derivation — transcribed from the
  5.3.0 wheel the native lane installs, in `fixtures/wrapper_spm.py` — with
  a golden, per-field rotation, a non-ASCII scenario, and a skipped case
  that starts asserting real equality the moment an SPM-capable wrapper is
  pinned. Hermetic CI now runs `compute_baseline_impl` under a real
  selection with a container that names its artifact the wrapper's way, so
  the guard *passing* is the claim, not only the abort. The native smoke
  makes the same claim against the real wrapper.
- **Medium 4** (`94e980e`): per-year child injection seams and four cases
  covering the typed child-call failure, the typed receipt-validation
  failure, and the redaction fallback on each.
- **Low 1** (`b074b95`): `_bundle_payload` drops the `spm` key from raw
  202/500 job bodies and the worker `_metadata` when a route has no
  capability, so a legacy no-SPM body is byte-identical to base; a
  canonical route still carries the capability.
- **Low 2** (`215d6fa`): the resolver carries why it refuses, the gateway
  README tells callers pinning an old version what to do, and cases pin the
  refusal, the accepted route it is distinguished from, and all four ways a
  manifest can state nothing. The same commit made "states nothing" mean
  one thing: a blank manifest entry had produced a 400 naming no version.
- **Low 3** (`0c3f9c6`): `tests/test_segmented_national.py` drives a
  segmented national reduce with SPM children end to end.
- **Low 4** (`638b7c6`, `3b28b9a`): a test double supplies the canonical
  wrapper's SPM surface and restore timing, so every decision `ensure()`
  makes about a receipt is fixed without the native source; the cache key
  and snapshot replacement are under test too.
- **Low 5** (`19e27f8`): `runtime_spm_capability` and the selection
  prevalidation are memoized on the installed image and on the resolved
  selection plus year range. Neither cache keeps exceptions, so fail-closed
  is unchanged, and the executor suite clears both around every test.

## Re-audit pass (`fd869e7`)

- The skipped `test_spm_arm_matches_the_installed_wrapper` claimed it would
  self-activate on a canonical pin. It would have raised instead: that
  wrapper's `spm_config` refuses a non-US model version. It now supplies
  the model version and the bundle the property re-resolves through.
- The precompute write-path test restated the identity's expression by
  hand, so three mutations of the real `storage_id` left the precompute
  suite green. It now builds a real `BaselineArtifactIdentity`; all three
  fail it.
- The scheduler's typed branches ran only at `max_parallel=1`, so the early
  return and the state write were both unpinned. Two cases now cover them.
- Agreement with the real wrapper is recorded, not just transcribed: eight
  selection shapes resolve to the same config and storage id through the
  qualification lane's 5.3.0 wheel and through this repo.

## Not changed, deliberately

- `changelog_entry.yaml`: no workflow, script or doc consumes it, there is
  no `CHANGELOG.md`, and `AGENTS.md` states there is no repository-wide
  changelog fragment requirement. Low 2's "changelog/doc note" is the
  gateway README section.
- `libs/policyengine-fastapi/src` carries nine pre-existing `ruff check`
  F401s, present at the PR head and on `main`. CI's lint job runs
  `ruff format --check` only, which passes.
