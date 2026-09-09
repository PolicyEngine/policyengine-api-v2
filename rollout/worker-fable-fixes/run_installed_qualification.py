"""Four-person worker and lazy-year smoke against new exact installed candidate wheels."""

# Imports below authentication must run after the explicit development bootstrap.
# ruff: noqa: E402

import hashlib
import importlib
import importlib.metadata as metadata
import importlib.util
import json
import os
from pathlib import Path
import sys
import subprocess
import zipfile

OUT = Path(__file__).resolve().parent
QUALIFICATION = Path(
    "/Users/maxghenis/spm-rebuild-20260908/rollout/year-boundary-qualification"
)
ROLLOUT = QUALIFICATION.parent
WORKTREES = ROLLOUT.parent / "worktrees"
WORKER = WORKTREES / "policyengine-sim-api-canonical"
SOURCE = ROLLOUT / "producer-final-candidate-20260909/artifacts/populace_us_2024.h5"
CONTENT = "3d86d5c4c0423480e6b69b75d222ffa4a7a2639e4094df5ba2504af01be17173"
WHEELS = {
    "policyengine": (
        ROLLOUT / "postfix-qualification/wheels/policyengine-5.3.0-py3-none-any.whl",
        "8c640d967575dddad70840bcbe938cea251c56958eded647c83eb9c5902735f1",
    ),
    "policyengine_us": (
        ROLLOUT
        / "postfix-qualification/wheels/policyengine_us-1.824.7-py3-none-any.whl",
        "7644819916a4f8ca2aa37a4a9d992fa834bfa66ab2d441326a9686baa5c1a688",
    ),
    "spm_calculator": (
        QUALIFICATION / "wheels/spm_calculator-1.0.0-py3-none-any.whl",
        "c49c41da5fd482e563eaea956e205a3ba6841cadd4dd32bef4c0c3dbce17ffba",
    ),
    "policyengine_core": (
        ROLLOUT
        / "postfix-qualification/wheels/policyengine_core-3.30.1-py3-none-any.whl",
        "2dbcf5f590a0199a7b7c77fcbbda2ff6bc289f6c6169ca0af3beace35d8b3e63",
    ),
}


def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


sys.dont_write_bytecode = True
os.environ["PYTHONDONTWRITEBYTECODE"] = "1"
os.environ["POLICYENGINE_SKIP_COUNTRY_IMPORTS"] = "1"
os.environ["SPM_NATIVE_SMOKE_SOURCE"] = str(SOURCE)
assert not os.environ.get("PYTHONPATH"), "No inherited source overlays allowed"
assert Path("/tmp").resolve() not in {Path(path).resolve() for path in sys.path}, (
    "Temporary-directory modules must not shadow installed dependencies"
)
for relative in (
    "projects/policyengine-simulation-executor/src",
    "projects/policyengine-simulation-entry/src",
    "projects/policyengine-simulation-gateway/src",
    "libs/policyengine-simulation-contract/src",
    "libs/policyengine-simulation-observability/src",
    "libs/policyengine-fastapi/src",
):
    sys.path.insert(0, str(WORKER / relative))

receipt = {
    "worker_head": subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=WORKER, text=True
    ).strip(),
    "scope": "four_person_native_worker_installed_candidate_wheel_qualification",
    "data_certification": "not_certified",
    "external_package_publication": "not_attested",
    "population_acceptance": "not_attested",
    "python": sys.executable,
    "wheels": {},
    "worker_source_overlay_only": True,
}
for module_name, (wheel, expected_hash) in WHEELS.items():
    assert sha256(wheel) == expected_hash, wheel
    dist = metadata.distribution(module_name)
    members = {}
    with zipfile.ZipFile(wheel) as archive:
        for member in archive.namelist():
            if not member.startswith(module_name + "/") or member.endswith("/"):
                continue
            installed = Path(dist.locate_file(member)).resolve()
            assert installed.is_relative_to(QUALIFICATION / "venv"), installed
            expected = archive.read(member)
            assert installed.read_bytes() == expected, installed
            members[member] = hashlib.sha256(expected).hexdigest()
    assert members, module_name
    spec = importlib.util.find_spec(module_name)
    assert Path(spec.origin).resolve().is_relative_to(QUALIFICATION / "venv"), (
        spec.origin
    )
    receipt["wheels"][module_name] = {
        "path": str(wheel),
        "sha256": expected_hash,
        "version": dist.version,
        "package_file_count": len(members),
        "installed_package_files": members,
        "import_origin_before": spec.origin,
    }

helper = WORKTREES / "policyengine-wrapper-production/tests/fixtures/spm_development.py"
spec = importlib.util.spec_from_file_location(
    "worker_spm_development_bootstrap", helper
)
bootstrap = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bootstrap)
manifest = QUALIFICATION / "development-manifest.json"
bootstrap.activate_spm_development_manifest(manifest)
receipt["development_fixture"] = {
    "manifest_path": str(manifest),
    "manifest_sha256": sha256(manifest),
    "bootstrap_path": str(helper),
    "bootstrap_sha256": sha256(helper),
    "compatibility_basis": "unverified_development_fixture",
}
for name in WHEELS:
    module = importlib.import_module(name)
    origin = str(Path(module.__file__).resolve())
    assert Path(origin).is_relative_to(QUALIFICATION / "venv"), origin
    receipt["wheels"][name]["import_origin_after"] = origin

from spm_calculator import load_forecast
from policyengine_simulation_executor.spm import runtime_spm_capability

assert load_forecast(expected_sha256=CONTENT).content_sha256 == CONTENT
capability = runtime_spm_capability()
assert capability.defaults.forecast_content_sha256 == CONTENT
receipt["runtime_capability"] = capability.model_dump(mode="json")
receipt["source_h5_sha256_before"] = sha256(SOURCE)
assert (
    receipt["source_h5_sha256_before"]
    == "6496cc4393d4d3c6574f76eca231de5898c803b9067645591fd5c4d3e65aee84"
)

import pandas as pd

with pd.HDFStore(SOURCE, "r") as source:
    household = source.select("household", start=0, stop=1)
    household_id = int(household.household_id.iloc[0])
    people = source.select("person", where=f"person_household_id == {household_id}")
    receipt["selected_households"] = len(household)
    receipt["selected_people"] = len(people)
    assert len(household) == 1 and len(people) == 4

import pytest


class OutcomeRecorder:
    def __init__(self):
        self.passed = []
        self.failed = []
        self.skipped = []

    def pytest_runtest_logreport(self, report):
        if report.skipped:
            self.skipped.append(report.nodeid)
        elif report.failed:
            self.failed.append(report.nodeid)
        elif report.when == "call" and report.passed:
            self.passed.append(report.nodeid)


outcomes = OutcomeRecorder()
exit_code = pytest.main(
    [
        str(
            WORKER
            / "projects/policyengine-simulation-executor/tests/test_canonical_spm_native.py"
        ),
        str(QUALIFICATION / "test_installed_year_boundary.py"),
        str(
            WORKER
            / "projects/policyengine-simulation-executor/tests/test_baseline_artifacts_spm_native.py"
        ),
        str(
            WORKER
            / "projects/policyengine-simulation-executor/tests/test_spm_runtime_native.py"
        ),
        "-q",
        "--basetemp",
        str(OUT / "pytest-native"),
        "-p",
        "no:cacheprovider",
    ],
    plugins=[outcomes],
)
receipt["pytest_outcomes"] = vars(outcomes)
assert not outcomes.skipped, outcomes.skipped
assert len(outcomes.passed) >= 15 and not outcomes.failed, vars(outcomes)
receipt["pytest_exit_code"] = int(exit_code)
source_files = subprocess.check_output(
    ["git", "ls-files", "projects", "libs"], cwd=WORKER, text=True
).splitlines()
receipt["worker_source_files"] = {
    name: sha256(WORKER / name)
    for name in source_files
    if name.endswith(".py")
    and ("/src/" in name or "/tests/" in name or "/fixtures/" in name)
}
receipt["qualification_harness_sha256"] = sha256(Path(__file__))
receipt["source_h5_sha256_after"] = sha256(SOURCE)
assert receipt["source_h5_sha256_after"] == receipt["source_h5_sha256_before"]
(OUT / "native-wheel-receipt.json").write_text(
    json.dumps(receipt, indent=2, sort_keys=True) + "\n"
)
raise SystemExit(exit_code)
