# PR #677 Fable-review fixes — progress

Branch: `max/spm-simulation-canonical-fixes-20260911` (from PR head `b0447ca`)
Target PR branch: `max/spm-simulation-canonical-20260909`
Base: `main` = `414c631d622f5f587eedd187296a80182a923db2`

## State

Worktree created at PR head. Investigating the nine review findings.

## Findings checklist

- [x] Medium 1 — completed results drop explicit nulls from `spm_config` on the wire
- [ ] Medium 2 — legacy no-SPM provenance `legacy-seed` expires on next publish
- [ ] Medium 3 — precompute storage identity never shown to match the wrapper
- [ ] Medium 4 — budget-window scheduler typed-error branches untested
- [x] Low 1 — legacy no-SPM poll bodies not byte-identical to base
- [ ] Low 2 — stale country routes now fail; undocumented, untested
- [ ] Low 3 — segmented reduce with SPM children untested end to end
- [ ] Low 4 — hermetic CI never exercises receipt validation in `ensure()`
- [ ] Low 5 — repeated prevalidation per request (perf)

## Done

- Created worktree, verified head/base SHAs.
- Baseline suites green at PR head: contract 73, gateway 149, entry 70,
  executor 456 passed / 22 skipped.
- **Medium 1**: `SPMSelection.serialize_selection` now restores options that
  were explicitly selected as null when the caller serializes with
  `exclude_none` (the poll routes do, via `response_model_exclude_none`).
  Tests: `test_completed_result_body_keeps_resolved_nulls`,
  `test_completed_budget_window_rows_keep_resolved_nulls` — both verified
  failing against the pre-fix serializer.
- **Low 1**: new `_bundle_payload` helper drops the `spm` key from raw 202/500
  job bodies and the worker `_metadata` when a route has no capability, so a
  legacy no-SPM body is byte-identical to base. Tests:
  `test_legacy_poll_bodies_carry_no_spm_key`,
  `test_legacy_budget_window_metadata_carries_no_spm_key`,
  `test_canonical_poll_bodies_still_carry_the_capability` — the first two
  verified failing against the pre-fix endpoints.

## Next

- Medium 2 (durable legacy-route provenance), Medium 3, Medium 4, Low 2-5.
