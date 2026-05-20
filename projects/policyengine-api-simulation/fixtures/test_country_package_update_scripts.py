"""Fixtures and helpers for country package updater script tests."""

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
