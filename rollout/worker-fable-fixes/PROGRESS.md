# PR677 Fable fixes

## State

- Authorized continuation from dcfe4fd89d97145882cb147a9aa2ffae2cd10ebf on max/spm-simulation-canonical-20260909.
- Exact Fable review read: gate 20260909-170551-pr-abdf4629, round 001-4542bf03eca1. Findings are valid; dispatch BrokenPipeError means no gate agreement exists.
- Existing untracked root PROGRESS.md and WORKER-CANONICAL-SPM-HANDOFF.md are preserved without edits. This committed progress file tracks this continuation.
- Initial git fetch origin and gh repo view failed because GitHub DNS/API connectivity is unavailable in the shell. The authenticated GitHub connector independently confirms live main is 414c631d622f5f587eedd187296a80182a923db2, identical to local origin/main, and PR677 is still a canonical draft at the requested starting head. Issue #676 is open and appropriate. Git transport remains pending.
- No browser, population job, publication, deployment, merge, .err or .lane.log reads.

## Done

- Inspected status, remotes, starting HEAD, and attempted upstream fetch before edits.
- Read repository AGENTS.md and canonical testing/GitHub PR skills; read exact reviewer output.
- Read installed PolicyEngine analysis, standards and API skills, parent PolicyEngine guidance and wrapper repository guidance. Repository-specific instructions and the user's bounded qualification scope govern this work.
- Committed an isolated qualification harness that authenticates the existing c49c/76448/8c640/2dbc wheels and reuses the existing explicit development bootstrap without modifying it, the packages, or historical evidence.
- Routing regressions before fixes: 13 gateway failures (historical routes, sibling ambiguity, malformed capability) and two partial-selection failures reproduced.
- Archived starting source to /tmp/worker-fable-base for like-for-like installed-environment type diagnostics; no checkout or handoff edits.
- Routing and runtime fixes committed, including adversarial follow-up for malformed seed schemas, future prefixed apps with absent routes, and unclassified sibling metadata. Latest full gateway suite: 149 passed; contract: 73 passed; entry: 66 passed; actual regenerated client: four passed.
- Full executor suite: 454 passed, 22 explicitly gated native tests skipped, two integration cases deselected, one environment-dependent version-extraction failure. That exact test passed with UV_NO_SYNC=1 against the existing environment (no download or package mutation), completing 455 unit checks.
- ./scripts/generate-clients.sh completed successfully; refreshed stale gateway OpenAPI golden and strengthened entry/gateway comparison to include SPM schemas.
- Clean native runtime regressions: eight failures before repair, then 56 canonical/runtime checks passed with zero skips. Earlier /tmp launchers were superseded after discovering unrelated pre-existing /tmp/h2.py import shadowing; clean launchers use safe-path mode and explicit installed Python 3.13.
- Clean artifact regressions reproduced receipt/column/cache-selection/storage identity failures. Artifact fixes and full native qualification are completing.
- Installed uv pip check: 180 compatible distributions. Current source Pyright: entry/contract zero errors; executor 145 and gateway 78, exactly matching unchanged starting source diagnostics.

## Next

- Add failing regressions and fix legacy route classification, typed runtime year/scenario errors, incomplete artifact recomputation, and precompute storage identity checks.
- Disposition related ambiguity, malformed capability, and partial-selection notes.
- Run focused and installed-environment qualifications, lint, type, and format checks; record source binding and exact evidence.
- Commit coherent steps; push verified commits to existing canonical draft PR677 and update its body if connectivity permits.
- Write FINAL-REPORT.md in this directory.
