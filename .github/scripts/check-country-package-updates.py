#!/usr/bin/env python3
"""Format country package changelog entries between two versions."""

from __future__ import annotations

import argparse
import re
import sys
import urllib.error
import urllib.request

REPO_MAP = {
    "policyengine-us": "PolicyEngine/policyengine-us",
    "policyengine-uk": "PolicyEngine/policyengine-uk",
}


def fetch_changelog(package: str) -> str | None:
    repo = REPO_MAP.get(package)
    if repo is None:
        return None

    for branch in ("main", "master"):
        url = f"https://raw.githubusercontent.com/{repo}/{branch}/CHANGELOG.md"
        try:
            with urllib.request.urlopen(url, timeout=30) as response:
                if response.status == 200:
                    return response.read().decode("utf-8")
        except (TimeoutError, urllib.error.URLError):
            continue

    return None


def parse_version(version: str) -> tuple[int, int, int]:
    parts = tuple(int(part) for part in version.split("."))
    if len(parts) != 3:
        raise ValueError(f"Expected a semantic version, got {version!r}")
    return parts


def parse_changelog(text: str) -> list[dict[str, object]]:
    entries: list[dict[str, object]] = []
    current_entry: dict[str, object] | None = None
    current_category: str | None = None

    for line in text.splitlines():
        version_match = re.match(r"^##\s+\[?(\d+\.\d+\.\d+)\]?", line)
        if version_match:
            current_entry = {"version": version_match.group(1), "changes": {}}
            entries.append(current_entry)
            current_category = None
            continue

        if current_entry is None:
            continue

        category_match = re.match(r"^###\s+(.+)", line)
        if category_match:
            current_category = category_match.group(1).strip().lower()
            continue

        item_match = re.match(r"^-\s+(.+)", line)
        if item_match and current_category:
            changes = current_entry["changes"]
            assert isinstance(changes, dict)
            changes.setdefault(current_category, [])
            changes[current_category].append(item_match.group(1))

    return entries


def get_changes_between(
    changelog: list[dict[str, object]], old_version: str, new_version: str
) -> list[dict[str, object]]:
    old_v = parse_version(old_version)
    new_v = parse_version(new_version)
    entries = []
    for entry in changelog:
        version = entry.get("version")
        if isinstance(version, str) and old_v < parse_version(version) <= new_v:
            entries.append(entry)
    return entries


def format_changes(entries: list[dict[str, object]]) -> str:
    preferred_order = ("added", "changed", "fixed", "removed", "deprecated")
    buckets: dict[str, list[str]] = {category: [] for category in preferred_order}
    extra_buckets: dict[str, list[str]] = {}

    for entry in entries:
        changes = entry.get("changes", {})
        if not isinstance(changes, dict):
            continue
        for category, items in changes.items():
            if not isinstance(category, str) or not isinstance(items, list):
                continue
            target = buckets if category in buckets else extra_buckets
            target.setdefault(category, [])
            target[category].extend(str(item) for item in items)

    sections = []
    for category in (*preferred_order, *sorted(extra_buckets)):
        items = buckets.get(category) or extra_buckets.get(category) or []
        if items:
            body = "\n".join(f"- {item}" for item in items)
            sections.append(f"### {category.capitalize()}\n{body}")

    return "\n\n".join(sections)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--package", required=True)
    parser.add_argument("--old-version", required=True)
    parser.add_argument("--new-version", required=True)
    args = parser.parse_args()

    changelog_text = fetch_changelog(args.package)
    if changelog_text is None:
        print(f"Could not fetch changelog for {args.package}.", file=sys.stderr)
        return 0

    changes = get_changes_between(
        parse_changelog(changelog_text), args.old_version, args.new_version
    )
    if not changes:
        print("No changelog entries found between these versions.")
        return 0

    print(format_changes(changes))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
