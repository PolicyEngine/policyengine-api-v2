#!/usr/bin/env bash
#
# Check PyPI for a newer country package, update the simulation project pins,
# and open a version-specific PR.
#
# Usage:
#   .github/scripts/update-country-package.sh policyengine-us [--dry-run]
#   .github/scripts/update-country-package.sh policyengine-uk [--dry-run]
#
# Optional environment:
#   PROJECT_DIR      Project containing pyproject.toml and uv.lock.
#   LATEST_OVERRIDE  Version to use instead of querying PyPI, for local checks.
#   DRY_RUN=1        Report planned changes without editing files or opening a PR.

set -euo pipefail

PACKAGE="${1:?Usage: update-country-package.sh <policyengine-us|policyengine-uk> [--dry-run]}"
DRY_RUN="${DRY_RUN:-0}"
if [[ "${2:-}" == "--dry-run" ]]; then
  DRY_RUN=1
fi

case "$PACKAGE" in
  policyengine-us)
    DISPLAY_NAME="PolicyEngine US"
    CONSTANT_NAME="US_VERSION"
    ENV_NAME="POLICYENGINE_US_VERSION"
    ;;
  policyengine-uk)
    DISPLAY_NAME="PolicyEngine UK"
    CONSTANT_NAME="UK_VERSION"
    ENV_NAME="POLICYENGINE_UK_VERSION"
    ;;
  *)
    echo "ERROR: Unsupported package '${PACKAGE}'." >&2
    exit 1
    ;;
esac

ROOT_DIR="$(git rev-parse --show-toplevel)"
PROJECT_DIR="${PROJECT_DIR:-projects/policyengine-api-simulation}"
PROJECT_PATH="${ROOT_DIR}/${PROJECT_DIR}"
PYPROJECT="${PROJECT_PATH}/pyproject.toml"
LOCKFILE="${PROJECT_PATH}/uv.lock"
MODAL_APP="${PROJECT_PATH}/src/modal/app.py"
CHANGELOG_DIR="${PROJECT_PATH}/changelog.d"

create_pr_body_file() {
  local changelog
  local pr_body_file

  changelog=$(python3 "${ROOT_DIR}/.github/scripts/check-country-package-updates.py" \
    --package "$PACKAGE" \
    --old-version "$CURRENT" \
    --new-version "$LATEST" 2>/dev/null || true)

  pr_body_file="$(mktemp)"
  {
    echo "## Summary"
    echo
    echo "Update ${DISPLAY_NAME} from ${CURRENT} to ${LATEST} in the simulation API runtime."
    if [[ -n "$changelog" ]]; then
      echo
      echo "## What changed (${CURRENT} -> ${LATEST})"
      echo
      echo "$changelog"
    fi
    echo
    echo "---"
    echo "Generated automatically by GitHub Actions."
  } > "$pr_body_file"

  echo "$pr_body_file"
}

if [[ ! -f "$PYPROJECT" || ! -f "$LOCKFILE" || ! -f "$MODAL_APP" ]]; then
  echo "ERROR: Expected simulation project files were not found under ${PROJECT_DIR}." >&2
  exit 1
fi

CURRENT=$(python3 - "$LOCKFILE" "$PACKAGE" <<'PY'
import re
import sys

lockfile, package = sys.argv[1:]
text = open(lockfile, encoding="utf-8").read()
pattern = rf'\[\[package\]\]\s+name = "{re.escape(package)}"\s+version = "([^"]+)"'
match = re.search(pattern, text)
if not match:
    raise SystemExit(f"Package {package!r} not found in {lockfile}")
print(match.group(1))
PY
)

if [[ -n "${LATEST_OVERRIDE:-}" ]]; then
  LATEST="$LATEST_OVERRIDE"
else
  LATEST=$(curl -fsSL "https://pypi.org/pypi/${PACKAGE}/json" | python3 -c 'import json, sys; print(json.load(sys.stdin)["info"]["version"])')
  if [[ -z "$LATEST" ]]; then
    echo "ERROR: Could not fetch latest version for ${PACKAGE} from PyPI." >&2
    exit 1
  fi
fi

if [[ -z "$LATEST" ]]; then
  echo "ERROR: Latest version for ${PACKAGE} is empty." >&2
  exit 1
fi

echo "Current locked version: ${PACKAGE}==${CURRENT}"
echo "Latest PyPI version:   ${PACKAGE}==${LATEST}"

if [[ "$CURRENT" == "$LATEST" ]]; then
  echo "Already up to date. Nothing to do."
  exit 0
fi

BRANCH="auto/update-${PACKAGE}-${LATEST}"
CHANGELOG_FRAGMENT="${CHANGELOG_DIR}/update-${PACKAGE}-${LATEST}.changed.md"
echo "Update available: ${CURRENT} -> ${LATEST}"

if [[ "$DRY_RUN" == "1" ]]; then
  if git ls-remote --exit-code --heads origin "$BRANCH" >/dev/null 2>&1; then
    echo "Dry run: remote branch '${BRANCH}' already exists; would ensure a PR exists for it."
    exit 0
  fi
  echo "Dry run: would create ${BRANCH} and update:"
  echo "  ${PROJECT_DIR}/pyproject.toml"
  echo "  ${PROJECT_DIR}/uv.lock"
  echo "  ${PROJECT_DIR}/src/modal/app.py"
  echo "  ${PROJECT_DIR}/changelog.d/$(basename "$CHANGELOG_FRAGMENT")"
  exit 0
fi

EXISTING_PR=$(gh pr list \
  --head "$BRANCH" \
  --state open \
  --json number \
  --jq '.[0].number' 2>/dev/null || true)
if [[ -n "$EXISTING_PR" ]]; then
  echo "PR #${EXISTING_PR} already exists for ${BRANCH}. Skipping."
  exit 0
fi

if git ls-remote --exit-code --heads origin "$BRANCH" >/dev/null 2>&1; then
  echo "Remote branch '${BRANCH}' already exists without an open PR. Creating PR."
  PR_BODY_FILE="$(create_pr_body_file)"
  gh pr create \
    --base main \
    --head "$BRANCH" \
    --title "chore(deps): update ${PACKAGE} to ${LATEST}" \
    --body-file "$PR_BODY_FILE"
  echo "PR created for existing branch ${BRANCH}"
  exit 0
fi

git config user.name "github-actions[bot]"
git config user.email "github-actions[bot]@users.noreply.github.com"
git checkout -b "$BRANCH"

python3 - "$PYPROJECT" "$MODAL_APP" "$PACKAGE" "$CURRENT" "$LATEST" "$CONSTANT_NAME" "$ENV_NAME" <<'PY'
import re
import sys
from pathlib import Path

pyproject_path, modal_app_path, package, current, latest, constant, env_name = sys.argv[1:]

pyproject = Path(pyproject_path)
pyproject_text = pyproject.read_text(encoding="utf-8")
old_pin = f'"{package}=={current}"'
new_pin = f'"{package}=={latest}"'
if old_pin not in pyproject_text:
    raise SystemExit(f"Could not find {old_pin} in {pyproject}")
pyproject.write_text(pyproject_text.replace(old_pin, new_pin), encoding="utf-8")

modal_app = Path(modal_app_path)
modal_text = modal_app.read_text(encoding="utf-8")
pattern = rf'{constant} = os\.environ\.get\("{env_name}", "[^"]+"\)'
replacement = f'{constant} = os.environ.get("{env_name}", "{latest}")'
updated, count = re.subn(pattern, replacement, modal_text, count=1)
if count != 1:
    raise SystemExit(f"Could not update {constant} in {modal_app}")
modal_app.write_text(updated, encoding="utf-8")
PY

(
  cd "$PROJECT_PATH"
  uv lock --upgrade-package "$PACKAGE"
)

mkdir -p "$CHANGELOG_DIR"
echo "Update ${DISPLAY_NAME} to ${LATEST}." > "$CHANGELOG_FRAGMENT"

if git diff --quiet -- "$PYPROJECT" "$LOCKFILE" "$MODAL_APP" "$CHANGELOG_FRAGMENT"; then
  echo "No changes after update. Nothing to do."
  exit 0
fi

PR_BODY_FILE="$(create_pr_body_file)"

git add "$PYPROJECT" "$LOCKFILE" "$MODAL_APP" "$CHANGELOG_FRAGMENT"
git commit -m "chore(deps): update ${PACKAGE} to ${LATEST}"
git push -u origin "$BRANCH"

gh pr create \
  --base main \
  --title "chore(deps): update ${PACKAGE} to ${LATEST}" \
  --body-file "$PR_BODY_FILE"

echo "PR created for ${PACKAGE} ${CURRENT} -> ${LATEST}"
