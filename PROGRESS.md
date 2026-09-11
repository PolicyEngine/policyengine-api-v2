# PR #677 Fable-review fixes — progress

Branch: `max/spm-simulation-canonical-fixes-20260911` (from PR head `b0447ca`)
Target PR branch: `max/spm-simulation-canonical-20260909`
Base: `main` = `414c631d622f5f587eedd187296a80182a923db2`

## State

Worktree created at PR head. Investigating the nine review findings.

## Findings checklist

- [ ] Medium 1 — completed results drop explicit nulls from `spm_config` on the wire
- [ ] Medium 2 — legacy no-SPM provenance `legacy-seed` expires on next publish
- [ ] Medium 3 — precompute storage identity never shown to match the wrapper
- [ ] Medium 4 — budget-window scheduler typed-error branches untested
- [ ] Low 1 — legacy no-SPM poll bodies not byte-identical to base
- [ ] Low 2 — stale country routes now fail; undocumented, untested
- [ ] Low 3 — segmented reduce with SPM children untested end to end
- [ ] Low 4 — hermetic CI never exercises receipt validation in `ensure()`
- [ ] Low 5 — repeated prevalidation per request (perf)

## Done

- Created worktree, verified head/base SHAs.

## Next

- Deep-read each finding site; write fixes with regression tests.
