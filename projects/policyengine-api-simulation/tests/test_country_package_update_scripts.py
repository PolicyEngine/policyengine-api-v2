"""Unit tests for country package updater scripts."""

from __future__ import annotations

import importlib.util
import os
import subprocess
from pathlib import Path
from types import ModuleType

import pytest

from fixtures.test_modal_scripts import REPO_ROOT, SCRIPTS_DIR


SCRIPT = SCRIPTS_DIR / "update-country-package.sh"
CHANGELOG_SCRIPT = SCRIPTS_DIR / "check-country-package-updates.py"


@pytest.fixture
def changelog_module() -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        "check_country_package_updates", CHANGELOG_SCRIPT
    )
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def fake_repo(tmp_path: Path) -> Path:
    project = tmp_path / "simulation"
    modal_dir = project / "src" / "modal"
    modal_dir.mkdir(parents=True)

    (project / "pyproject.toml").write_text(
        "\n".join(
            [
                "[project]",
                'dependencies = ["policyengine-us==1.0.0", "policyengine-uk==2.0.0"]',
            ]
        ),
        encoding="utf-8",
    )
    (project / "uv.lock").write_text(
        "\n".join(
            [
                "[[package]]",
                'name = "policyengine-us"',
                'version = "1.0.0"',
                "",
                "[[package]]",
                'name = "policyengine-uk"',
                'version = "2.0.0"',
            ]
        ),
        encoding="utf-8",
    )
    (modal_dir / "app.py").write_text(
        "\n".join(
            [
                "import os",
                'US_VERSION = os.environ.get("POLICYENGINE_US_VERSION", "1.0.0")',
                'UK_VERSION = os.environ.get("POLICYENGINE_UK_VERSION", "2.0.0")',
            ]
        ),
        encoding="utf-8",
    )

    helper_dir = tmp_path / ".github" / "scripts"
    helper_dir.mkdir(parents=True)
    (helper_dir / "check-country-package-updates.py").write_text(
        '#!/usr/bin/env python3\nprint("### Added\\n- Example upstream change")\n',
        encoding="utf-8",
    )

    return tmp_path


@pytest.fixture
def fake_bin(tmp_path: Path) -> Path:
    path = tmp_path / "bin"
    path.mkdir()
    return path


def write_executable(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")
    path.chmod(0o755)


def install_fake_git(
    fake_bin: Path,
    *,
    root: Path,
    log: Path,
    remote_branch_exists: bool = False,
    diff_has_changes: bool = False,
) -> None:
    write_executable(
        fake_bin / "git",
        f"""#!/usr/bin/env bash
set -euo pipefail
printf 'git %s\\n' "$*" >> "{log}"

if [[ "$1" == "rev-parse" && "$2" == "--show-toplevel" ]]; then
  echo "{root}"
  exit 0
fi

if [[ "$1" == "ls-remote" ]]; then
  if [[ "{int(remote_branch_exists)}" == "1" ]]; then
    exit 0
  fi
  exit 2
fi

if [[ "$1" == "diff" ]]; then
  if [[ "{int(diff_has_changes)}" == "1" ]]; then
    exit 1
  fi
  exit 0
fi

exit 0
""",
    )


def install_fake_gh(fake_bin: Path, *, log: Path, open_pr: str = "") -> None:
    write_executable(
        fake_bin / "gh",
        f"""#!/usr/bin/env bash
set -euo pipefail
printf 'gh %s\\n' "$*" >> "{log}"

if [[ "$1" == "pr" && "$2" == "list" ]]; then
  printf '%s\\n' "{open_pr}"
  exit 0
fi

if [[ "$1" == "pr" && "$2" == "create" ]]; then
  exit 0
fi

exit 0
""",
    )


def install_fake_uv(fake_bin: Path, *, log: Path) -> None:
    write_executable(
        fake_bin / "uv",
        f"""#!/usr/bin/env bash
set -euo pipefail
printf 'uv %s\\n' "$*" >> "{log}"
exit 0
""",
    )


def updater_env(fake_bin: Path, fake_repo: Path, **extra: str) -> dict[str, str]:
    env = os.environ.copy()
    env.update(
        {
            "PATH": f"{fake_bin}{os.pathsep}{env['PATH']}",
            "PROJECT_DIR": "simulation",
        }
    )
    env.update(extra)
    return env


def run_updater(*args: str, env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["bash", str(SCRIPT), *args],
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
    )


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
    assert "simulation/src/modal/app.py" in result.stdout
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
    modal_text = (fake_repo / "simulation" / "src" / "modal" / "app.py").read_text(
        encoding="utf-8"
    )
    assert "policyengine-us==1.1.0" in pyproject_text
    assert (
        'US_VERSION = os.environ.get("POLICYENGINE_US_VERSION", "1.1.0")' in modal_text
    )
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
    text = """
# Changelog

## 1.2.2
### Added
- New variable

### Fixed
- Important bug fix

## [1.2.1]
### Changed
- Existing calculation changed

## 1.2.0
### Added
- Old change
"""

    parsed = changelog_module.parse_changelog(text)
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
