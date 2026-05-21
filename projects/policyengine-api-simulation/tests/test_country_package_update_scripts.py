"""Unit tests for country package updater scripts."""

from __future__ import annotations

import subprocess
from pathlib import Path
from types import ModuleType

import pytest

from fixtures.test_country_package_update_scripts import (
    SAMPLE_CHANGELOG,
    SCRIPT,
    install_fake_gh,
    install_fake_git,
    install_fake_uv,
    run_updater,
    updater_env,
)

pytest_plugins = ("fixtures.test_country_package_update_scripts",)


def test_update_country_package_script_has_valid_bash_syntax() -> None:
    result = subprocess.run(
        ["bash", "-n", str(SCRIPT)],
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr


def test_update_country_package_rejects_unknown_package(
    fake_bin: Path, fake_repo: Path, tmp_path: Path
) -> None:
    git_log = tmp_path / "git.log"
    install_fake_git(fake_bin, root=fake_repo, log=git_log)

    result = run_updater(
        "policyengine-ca",
        env=updater_env(fake_bin, fake_repo, LATEST_OVERRIDE="1.1.0"),
    )

    assert result.returncode != 0
    assert "Unsupported package 'policyengine-ca'" in result.stderr


def test_update_country_package_dry_run_reports_planned_changes_without_editing(
    fake_bin: Path, fake_repo: Path, tmp_path: Path
) -> None:
    git_log = tmp_path / "git.log"
    install_fake_git(fake_bin, root=fake_repo, log=git_log)
    pyproject = fake_repo / "simulation" / "pyproject.toml"
    original_pyproject = pyproject.read_text(encoding="utf-8")

    result = run_updater(
        "policyengine-us",
        "--dry-run",
        env=updater_env(fake_bin, fake_repo, LATEST_OVERRIDE="1.1.0"),
    )

    assert result.returncode == 0, result.stderr
    assert "Update available: 1.0.0 -> 1.1.0" in result.stdout
    assert "Dry run: would create auto/update-policyengine-us-1.1.0" in result.stdout
    assert "simulation/pyproject.toml" in result.stdout
    assert "simulation/uv.lock" in result.stdout
    assert pyproject.read_text(encoding="utf-8") == original_pyproject


def test_update_country_package_dry_run_reports_existing_branch_recovery(
    fake_bin: Path, fake_repo: Path, tmp_path: Path
) -> None:
    git_log = tmp_path / "git.log"
    install_fake_git(
        fake_bin,
        root=fake_repo,
        log=git_log,
        remote_branch_exists=True,
    )

    result = run_updater(
        "policyengine-us",
        "--dry-run",
        env=updater_env(fake_bin, fake_repo, LATEST_OVERRIDE="1.1.0"),
    )

    assert result.returncode == 0, result.stderr
    assert (
        "remote branch 'auto/update-policyengine-us-1.1.0' already exists; "
        "would ensure a PR exists for it."
    ) in result.stdout


def test_update_country_package_skips_when_open_pr_exists(
    fake_bin: Path, fake_repo: Path, tmp_path: Path
) -> None:
    git_log = tmp_path / "git.log"
    gh_log = tmp_path / "gh.log"
    install_fake_git(fake_bin, root=fake_repo, log=git_log)
    install_fake_gh(fake_bin, log=gh_log, open_pr="123")

    result = run_updater(
        "policyengine-us",
        env=updater_env(fake_bin, fake_repo, LATEST_OVERRIDE="1.1.0"),
    )

    assert result.returncode == 0, result.stderr
    assert (
        "PR #123 already exists for auto/update-policyengine-us-1.1.0" in result.stdout
    )
    assert "pr create" not in gh_log.read_text(encoding="utf-8")


def test_update_country_package_opens_pr_for_existing_branch_without_open_pr(
    fake_bin: Path, fake_repo: Path, tmp_path: Path
) -> None:
    git_log = tmp_path / "git.log"
    gh_log = tmp_path / "gh.log"
    install_fake_git(
        fake_bin,
        root=fake_repo,
        log=git_log,
        remote_branch_exists=True,
    )
    install_fake_gh(fake_bin, log=gh_log)

    result = run_updater(
        "policyengine-us",
        env=updater_env(fake_bin, fake_repo, LATEST_OVERRIDE="1.1.0"),
    )

    assert result.returncode == 0, result.stderr
    assert "already exists without an open PR. Creating PR." in result.stdout
    gh_calls = gh_log.read_text(encoding="utf-8")
    assert "pr list" in gh_calls
    assert "pr create" in gh_calls
    assert "--head auto/update-policyengine-us-1.1.0" in gh_calls


def test_update_country_package_updates_files_and_opens_pr(
    fake_bin: Path, fake_repo: Path, tmp_path: Path
) -> None:
    git_log = tmp_path / "git.log"
    gh_log = tmp_path / "gh.log"
    uv_log = tmp_path / "uv.log"
    install_fake_git(fake_bin, root=fake_repo, log=git_log, diff_has_changes=True)
    install_fake_gh(fake_bin, log=gh_log)
    install_fake_uv(fake_bin, log=uv_log)

    result = run_updater(
        "policyengine-us",
        env=updater_env(fake_bin, fake_repo, LATEST_OVERRIDE="1.1.0"),
    )

    assert result.returncode == 0, result.stderr
    assert "PR created for policyengine-us 1.0.0 -> 1.1.0" in result.stdout

    pyproject_text = (fake_repo / "simulation" / "pyproject.toml").read_text(
        encoding="utf-8"
    )
    assert "policyengine-us==1.1.0" in pyproject_text
    assert "lock --upgrade-package policyengine-us" in uv_log.read_text(
        encoding="utf-8"
    )
    assert "checkout -b auto/update-policyengine-us-1.1.0" in git_log.read_text(
        encoding="utf-8"
    )
    assert "pr create" in gh_log.read_text(encoding="utf-8")


def test_parse_changelog_collects_versioned_category_items(
    changelog_module: ModuleType,
) -> None:
    parsed = changelog_module.parse_changelog(SAMPLE_CHANGELOG)
    changes = changelog_module.get_changes_between(parsed, "1.2.0", "1.2.2")
    formatted = changelog_module.format_changes(changes)

    assert "### Added\n- New variable" in formatted
    assert "### Changed\n- Existing calculation changed" in formatted
    assert "### Fixed\n- Important bug fix" in formatted
    assert "Old change" not in formatted


def test_parse_version_requires_three_numeric_parts(
    changelog_module: ModuleType,
) -> None:
    assert changelog_module.parse_version("1.2.3") == (1, 2, 3)

    with pytest.raises(ValueError, match="Expected a semantic version"):
        changelog_module.parse_version("1.2")


def test_fetch_changelog_returns_none_for_unknown_package(
    changelog_module: ModuleType,
) -> None:
    assert changelog_module.fetch_changelog("policyengine-ca") is None
