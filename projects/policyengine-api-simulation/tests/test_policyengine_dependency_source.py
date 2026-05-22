"""Regression tests for the policyengine dependency version configuration."""

import tomllib
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
PYPROJECT_PATH = REPO_ROOT / "pyproject.toml"
MODAL_APP_PATH = REPO_ROOT / "src" / "modal" / "app.py"
POLICYENGINE_DEPENDENCY_PREFIX = "policyengine=="
POLICYENGINE_CORE_DEPENDENCY_PREFIX = "policyengine-core=="
COUNTRY_PACKAGES = {
    "us": "policyengine-us",
    "uk": "policyengine-uk",
}


def _load_toml(path: Path) -> dict:
    with path.open("rb") as file:
        return tomllib.load(file)


def _get_pyproject_policyengine_dependency(pyproject: dict) -> str:
    dependencies = pyproject["project"]["dependencies"]
    return next(
        dep for dep in dependencies if dep.startswith(POLICYENGINE_DEPENDENCY_PREFIX)
    )


def _get_pyproject_policyengine_core_dependency(pyproject: dict) -> str:
    dependencies = pyproject["project"]["dependencies"]
    return next(
        dep
        for dep in dependencies
        if dep.startswith(POLICYENGINE_CORE_DEPENDENCY_PREFIX)
    )


def _get_dependency_pin(pyproject: dict, package: str) -> str:
    dependencies = pyproject["project"]["dependencies"]
    prefix = f"{package}=="
    return next(
        dep.removeprefix(prefix) for dep in dependencies if dep.startswith(prefix)
    )


def test_policyengine_dependency_version_is_pinned_consistently():
    from src.modal.dependency_pins import project_dependency_pin

    pyproject = _load_toml(PYPROJECT_PATH)
    pyproject_dependency = _get_pyproject_policyengine_dependency(pyproject)
    pyproject_core_dependency = _get_pyproject_policyengine_core_dependency(pyproject)

    assert pyproject_dependency.startswith(POLICYENGINE_DEPENDENCY_PREFIX)
    assert pyproject_core_dependency.startswith(POLICYENGINE_CORE_DEPENDENCY_PREFIX)
    assert (
        f"policyengine=={project_dependency_pin('policyengine')}"
        == pyproject_dependency
    )
    assert (
        f"policyengine-core=={project_dependency_pin('policyengine-core')}"
        == pyproject_core_dependency
    )


def test_modal_app_reads_policyengine_pins_from_pyproject():
    modal_source = MODAL_APP_PATH.read_text(encoding="utf-8")

    assert '"policyengine==4.10.0"' not in modal_source
    assert '"policyengine-core==3.26.1"' not in modal_source
    assert "project_dependency_pin" in modal_source
    assert '"policyengine"' in modal_source
    assert '"policyengine-core"' in modal_source


def test_country_package_pins_match_policyengine_bundle():
    from src.modal.release_bundle import get_country_release_bundle

    pyproject = _load_toml(PYPROJECT_PATH)

    for country, package in COUNTRY_PACKAGES.items():
        assert (
            _get_dependency_pin(pyproject, package)
            == get_country_release_bundle(country).model_version
        )
