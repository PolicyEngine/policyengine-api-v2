# Runtime year and scenario error evidence

State: Fable finding 2 fixed and verified against the authenticated installed calculator, country, core, and wrapper. Root-owned integrated qualification and final source binding remain separate.

Worker prevalidation now uses the installed `PolicyEngineSPMProvider.year_metadata` typed year contract. Its constructor still emits a plain unknown-scenario `ValueError`; the worker uses the same narrow scenario translation as the calculator's Frame and Axiom adapters. Other invalid settings retain `SPM_SETTINGS_INVALID`. The shared contract recognizes `SPM_SCENARIO_UNAVAILABLE` so transport does not redact that code. Scientific packages and their source were not changed.

The new native tests compare actual provider/Axiom errors with annual and budget-window worker entrypoints before dataset/child setup. They cover 2021, 2036, the `year=2040` alias, unavailable window starts and a 2035–2036 window end, unknown scenarios, and invalid as-of/vintage settings. The valid-year case forbids amount evaluation and checks that a fresh real provider still has empty receipt years. Existing HTTP, polling, pickle, country-error, and optional-output tests now include the scenario code. The parent integrated run also reuses the prior 12 installed provider/country tests, including actual out-of-range tax-only calculations followed by typed threshold failure.

## Clean regression and verification commands

```sh
env -u PYTHONPATH PYTHONSAFEPATH=1 UV_CACHE_DIR=/private/tmp/worker-fable-uv-cache uv run --no-project --python /Users/maxghenis/spm-rebuild-20260908/rollout/year-boundary-qualification/venv/bin/python /private/tmp/run_worker_runtime_regressions.py --original-runtime --basetemp /private/tmp/worker-runtime-clean-red > /private/tmp/worker-runtime-clean-red.txt 2>&1

env -u PYTHONPATH PYTHONSAFEPATH=1 UV_CACHE_DIR=/private/tmp/worker-fable-uv-cache uv run --no-project --python /Users/maxghenis/spm-rebuild-20260908/rollout/year-boundary-qualification/venv/bin/python /private/tmp/run_worker_runtime_regressions.py projects/policyengine-simulation-executor/tests/test_canonical_spm.py --basetemp /private/tmp/worker-runtime-clean-green > /private/tmp/worker-runtime-clean-green.txt 2>&1

UV_CACHE_DIR=/private/tmp/worker-fable-uv-cache uv run --project projects/policyengine-simulation-executor --no-sync ruff format projects/policyengine-simulation-executor/src/policyengine_simulation_executor/spm.py projects/policyengine-simulation-executor/tests/test_canonical_spm.py projects/policyengine-simulation-executor/tests/test_spm_runtime_native.py

UV_CACHE_DIR=/private/tmp/worker-fable-uv-cache uv run --project projects/policyengine-simulation-executor --no-sync ruff check projects/policyengine-simulation-executor/src/policyengine_simulation_executor/spm.py projects/policyengine-simulation-executor/tests/test_canonical_spm.py projects/policyengine-simulation-executor/tests/test_spm_runtime_native.py
```

The temporary launcher executes only the original qualification script's authenticated wheel/bootstrap setup (before `import pytest`) and invokes committed `tests/test_spm_runtime_native.py` with pytest `-q -p no:cacheprovider`. It asserts `/tmp` and `/private/tmp` are absent from `sys.path`. With `--original-runtime`, it overlays only the archived `dcfe4fd` executor `spm.py` from `/private/tmp/worker-fable-base`; it retains current shared transport recognition so the scenario regression reaches the original worker mapping itself. No checkout, installed-package edit, or fabricated metadata is involved.

- Clean RED: **8 failed, 3 passed, zero skipped, 2.12 seconds**. All six year and both scenario boundary cases fail on the original worker with `SPM_SETTINGS_INVALID` in place of the calculator code. Full output: `runtime-regression-red.txt`.
- Clean GREEN: **56 passed, zero skipped, 0.28 seconds** across the 11 native cases and 45 canonical worker/transport cases. Full output: `runtime-regression-green.txt`.
- Ruff formatting and lint: pass. The two pytest plugin-rewrite warnings reflect explicit bootstrap before pytest, as in the prior qualification.

## Superseded attempts and limits

The first launcher invocation safely stopped at the inherited-PYTHONPATH guard. A service-local `uv run --no-sync pytest tests/test_canonical_spm.py -q` attempt selected an ambient Python 3.14 tool and could not collect the missing contract package; it is not validation evidence. No environment was changed.

Early temporary-launcher RED/GREEN outputs lacked Python safe-path isolation: unrelated `/private/tmp/h2.py` shadowed optional HTTP/2 and imported an unrelated demonstration. Those outputs are superseded and are not qualification evidence. The unrelated files were not edited. The committed RED output was replaced by the clean isolated run above; both clean runs have no unrelated demo output. The final root-owned harness lives inside the repository and authenticates installed sources again.

Remaining coupling: the installed PolicyEngine adapter lacks a public typed scenario-selection validator, so the narrow scenario translation follows the real calculator adapters' current contract. The tests execute the public Axiom adapter to detect drift. No amount formulas, installed receipt metadata, publication, population execution, deployment, or merge changed.
