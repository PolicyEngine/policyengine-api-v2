"""Regression tests for the policyengine dependency version configuration."""

import tomllib
from pathlib import Path

from src.modal.policyengine_dependency import get_policyengine_dependency

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


def test_policyengine_dependency_version_is_read_from_pyproject():
    pyproject = _load_toml(PYPROJECT_PATH)
    pyproject_dependency = _get_pyproject_policyengine_dependency(pyproject)

    assert pyproject_dependency.startswith(POLICYENGINE_DEPENDENCY_PREFIX)
    assert get_policyengine_dependency() == pyproject_dependency


def test_modal_app_uses_shared_dependency_helper():
    modal_source = MODAL_APP_PATH.read_text()

    assert (
        "from src.modal.policyengine_dependency import get_policyengine_dependency"
        in modal_source
    )
    assert "POLICYENGINE_DEPENDENCY = get_policyengine_dependency()" in modal_source
    assert "POLICYENGINE_DEPENDENCY," in modal_source
