# Runtime year and scenario error evidence

State: regression reproduced against the authenticated installed calculator and country/wrapper environment; implementation pending.

The exact Fable reviewer output and repository testing skill were read. The installed `PolicyEngineSPMProvider.year_metadata` supplies the typed year contract. Its constructor still raises a plain unknown-scenario `ValueError`; the calculator's public Axiom `export_build_spec` translates that condition into `SPM_SCENARIO_UNAVAILABLE`. Worker prevalidation currently reports `SPM_SETTINGS_INVALID` instead and the shared error recognizer drops the scenario code entirely.

Regression-first command:

```sh
env -u PYTHONPATH UV_CACHE_DIR=/private/tmp/worker-fable-uv-cache uv run --no-project --python /Users/maxghenis/spm-rebuild-20260908/rollout/year-boundary-qualification/venv/bin/python /private/tmp/run_worker_runtime_regressions.py > /private/tmp/worker-runtime-regression-red.txt 2>&1
```

The temporary launcher executes only the original qualification script's authenticated wheel/bootstrap setup (before `import pytest`) and invokes the committed `tests/test_spm_runtime_native.py` with pytest `-q -p no:cacheprovider --basetemp /private/tmp/worker-runtime-regression-pytest`. It neither rewrites historical evidence nor modifies installed packages. Initial invocation with inherited PYTHONPATH stopped at the original bootstrap's explicit guard; rerun unsets it.

Result before fixes: **8 failed, 1 passed, zero skipped, 1.21 seconds**. Six annual/year-alias/budget-window start/end cases showed the wrong year code; two real calculator scenario-contract cases showed the missing public scenario-code recognition. Valid-year prevalidation performs no amount calculation. Two plugin-rewrite warnings reflect explicit bootstrap before pytest, as in the prior qualification.

Next: preserve typed adapter errors, test full public error transport, run the integrated installed qualification including the prior real-country lazy tax-only tests, and record final outcomes/source binding in the final report.
