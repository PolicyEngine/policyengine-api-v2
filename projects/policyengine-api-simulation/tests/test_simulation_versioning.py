"""Tests for simulation API release versioning helpers."""

from __future__ import annotations

import subprocess
from pathlib import Path

from fixtures.test_modal_scripts import REPO_ROOT


SCRIPT = (
    REPO_ROOT
    / "projects"
    / "policyengine-api-simulation"
    / "scripts"
    / "bump_version.py"
)


def make_project(tmp_path: Path, *fragments: str) -> Path:
    project = tmp_path / "simulation"
    changelog = project / "changelog.d"
    changelog.mkdir(parents=True)
    (project / "pyproject.toml").write_text(
        "\n".join(
            [
                "[project]",
                'name = "policyengine-simulation-api-project"',
                'version = "1.2.3"',
            ]
        ),
        encoding="utf-8",
    )
    for fragment in fragments:
        (changelog / fragment).write_text("Example change.\n", encoding="utf-8")
    return project


def run_bump(project: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["python", str(SCRIPT), str(project)],
        capture_output=True,
        text=True,
    )


def read_version(project: Path) -> str:
    return (project / "pyproject.toml").read_text(encoding="utf-8")


def test_bump_version_uses_patch_for_changed_fragments(tmp_path: Path) -> None:
    project = make_project(tmp_path, "country-package.changed.md")

    result = run_bump(project)

    assert result.returncode == 0, result.stderr
    assert 'version = "1.2.4"' in read_version(project)


def test_bump_version_uses_minor_for_added_fragments(tmp_path: Path) -> None:
    project = make_project(tmp_path, "feature.added.md")

    result = run_bump(project)

    assert result.returncode == 0, result.stderr
    assert 'version = "1.3.0"' in read_version(project)


def test_bump_version_uses_major_for_breaking_fragments(tmp_path: Path) -> None:
    project = make_project(tmp_path, "api-breaking.breaking.md")

    result = run_bump(project)

    assert result.returncode == 0, result.stderr
    assert 'version = "2.0.0"' in read_version(project)


def test_bump_version_fails_without_fragments(tmp_path: Path) -> None:
    project = make_project(tmp_path)

    result = run_bump(project)

    assert result.returncode != 0
    assert "No changelog fragments found" in result.stderr
