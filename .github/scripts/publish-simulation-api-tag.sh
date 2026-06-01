#!/bin/bash

set -euo pipefail

PROJECT_DIR="${1:-projects/policyengine-api-simulation}"
PYPROJECT="${PROJECT_DIR}/pyproject.toml"

VERSION=$(python - "$PYPROJECT" <<'PY'
import re
import sys
from pathlib import Path

text = Path(sys.argv[1]).read_text(encoding="utf-8")
match = re.search(r'^version\s*=\s*"([^"]+)"', text, re.MULTILINE)
if not match:
    raise SystemExit(f"Could not find version in {sys.argv[1]}")
print(match.group(1))
PY
)

TAG="policyengine-api-simulation-v${VERSION}"

git tag "$TAG" 2>/dev/null || true
git push origin "refs/tags/${TAG}" || true
