"""Regression tests for the policyengine dependency version configuration."""

import re
import tomllib
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
PYPROJECT_PATH = REPO_ROOT / "pyproject.toml"
MODAL_APP_PATH = REPO_ROOT / "src" / "modal" / "app.py"
POLICYENGINE_DEPENDENCY_PREFIX = "policyengine=="


def _load_toml(path: Path) -> dict:
    with path.open("rb") as file:
        return tomllib.load(file)


def _get_pyproject_policyengine_dependency(pyproject: dict) -> str:
    dependencies = pyproject["project"]["dependencies"]
    return next(
        dep for dep in dependencies if dep.startswith(POLICYENGINE_DEPENDENCY_PREFIX)
    )


def _get_modal_policyengine_dependency(modal_source: str) -> str:
    match = re.search(
        r'"(policyengine==[^"]+)"',
        modal_source,
    )
    assert match is not None, "Modal app should install a pinned policyengine version"
    return match.group(1)


def test_policyengine_dependency_version_is_pinned_consistently():
    pyproject = _load_toml(PYPROJECT_PATH)
    pyproject_dependency = _get_pyproject_policyengine_dependency(pyproject)
    modal_dependency = _get_modal_policyengine_dependency(MODAL_APP_PATH.read_text())

    assert pyproject_dependency.startswith(POLICYENGINE_DEPENDENCY_PREFIX)
    assert modal_dependency == pyproject_dependency
