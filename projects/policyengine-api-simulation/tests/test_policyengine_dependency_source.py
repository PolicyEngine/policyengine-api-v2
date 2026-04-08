"""Regression tests for the policyengine dependency source configuration."""

import re
import tomllib
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
PYPROJECT_PATH = REPO_ROOT / "pyproject.toml"
UV_LOCK_PATH = REPO_ROOT / "uv.lock"
MODAL_APP_PATH = REPO_ROOT / "src" / "modal" / "app.py"

POLICYENGINE_GIT_PREFIX = "policyengine @ git+https://github.com/PolicyEngine/policyengine.py@"


def _load_toml(path: Path) -> dict:
    with path.open("rb") as file:
        return tomllib.load(file)


def _get_pyproject_policyengine_dependency(pyproject: dict) -> str:
    dependencies = pyproject["project"]["dependencies"]
    return next(dep for dep in dependencies if dep.startswith("policyengine "))


def _get_modal_policyengine_dependency(modal_source: str) -> str:
    match = re.search(
        r'"(policyengine @ git\+https://github\.com/PolicyEngine/policyengine\.py@[0-9a-f]+)"',
        modal_source,
    )
    assert match is not None, "Modal app should install policyengine from a pinned Git commit"
    return match.group(1)


def test_policyengine_dependency_source_is_pinned_consistently():
    pyproject = _load_toml(PYPROJECT_PATH)
    pyproject_dependency = _get_pyproject_policyengine_dependency(pyproject)
    modal_dependency = _get_modal_policyengine_dependency(MODAL_APP_PATH.read_text())

    assert pyproject["tool"]["hatch"]["metadata"]["allow-direct-references"] is True
    assert pyproject_dependency.startswith(POLICYENGINE_GIT_PREFIX)
    assert modal_dependency == pyproject_dependency


def test_uv_lock_tracks_the_same_policyengine_git_revision():
    pyproject = _load_toml(PYPROJECT_PATH)
    uv_lock = _load_toml(UV_LOCK_PATH)
    pyproject_dependency = _get_pyproject_policyengine_dependency(pyproject)
    expected_revision = pyproject_dependency.removeprefix(POLICYENGINE_GIT_PREFIX)

    policyengine_package = next(
        package for package in uv_lock["package"] if package["name"] == "policyengine"
    )

    source = policyengine_package["source"]["git"]
    assert f"rev={expected_revision}" in source
    assert source.endswith(f"#{expected_revision}")
