"""Infer a semver bump from Towncrier fragments and update project version."""

from __future__ import annotations

import re
import sys
from pathlib import Path


def get_current_version(pyproject_path: Path) -> str:
    text = pyproject_path.read_text(encoding="utf-8")
    match = re.search(
        r'^version\s*=\s*"(\d+\.\d+\.\d+)"',
        text,
        re.MULTILINE,
    )
    if not match:
        print("Could not find version in pyproject.toml", file=sys.stderr)
        sys.exit(1)
    return match.group(1)


def infer_bump(changelog_dir: Path) -> str:
    fragments = [
        path
        for path in changelog_dir.iterdir()
        if path.is_file() and path.name != ".gitkeep"
    ]
    if not fragments:
        print("No changelog fragments found", file=sys.stderr)
        sys.exit(1)

    categories = {path.suffix.lstrip(".") for path in fragments}
    for path in fragments:
        parts = path.stem.split(".")
        if len(parts) >= 2:
            categories.add(parts[-1])

    if "breaking" in categories:
        return "major"
    if "added" in categories or "removed" in categories:
        return "minor"
    return "patch"


def bump_version(version: str, bump: str) -> str:
    major, minor, patch = (int(part) for part in version.split("."))
    if bump == "major":
        return f"{major + 1}.0.0"
    if bump == "minor":
        return f"{major}.{minor + 1}.0"
    return f"{major}.{minor}.{patch + 1}"


def update_version(pyproject_path: Path, old_version: str, new_version: str) -> None:
    text = pyproject_path.read_text(encoding="utf-8")
    updated = text.replace(
        f'version = "{old_version}"',
        f'version = "{new_version}"',
        1,
    )
    if updated == text:
        print(
            f"Could not update version in {pyproject_path}",
            file=sys.stderr,
        )
        sys.exit(1)
    pyproject_path.write_text(updated, encoding="utf-8")
    print(f"  Updated {pyproject_path}")


def main(argv: list[str] | None = None) -> None:
    args = sys.argv[1:] if argv is None else argv
    project_dir = (
        Path(args[0]).resolve() if args else Path(__file__).resolve().parent.parent
    )
    pyproject = project_dir / "pyproject.toml"
    changelog_dir = project_dir / "changelog.d"

    current = get_current_version(pyproject)
    bump = infer_bump(changelog_dir)
    new = bump_version(current, bump)

    print(f"Version: {current} -> {new} ({bump})")
    update_version(pyproject, current, new)


if __name__ == "__main__":
    main()
