"""Helpers for keeping the simulation service's policyengine pin in one place."""

from pathlib import Path
import tomllib

POLICYENGINE_DEPENDENCY_PREFIX = "policyengine=="
PROJECT_ROOT = Path(__file__).resolve().parents[2]
PYPROJECT_PATH = PROJECT_ROOT / "pyproject.toml"


def get_policyengine_dependency() -> str:
    """Read the pinned policyengine dependency from pyproject.toml."""
    with PYPROJECT_PATH.open("rb") as file:
        pyproject = tomllib.load(file)

    dependencies = pyproject["project"]["dependencies"]
    return next(
        dependency
        for dependency in dependencies
        if dependency.startswith(POLICYENGINE_DEPENDENCY_PREFIX)
    )
