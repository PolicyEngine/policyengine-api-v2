#!/usr/bin/env python
"""Generate OpenAPI clients using openapi-python-client."""

import subprocess
import sys
from pathlib import Path


def generate_python_client():
    """Generate Python client from OpenAPI spec."""
    project_dir = Path(__file__).parent
    spec_path = project_dir / "artifacts" / "openapi.json"
    output_dir = project_dir / "artifacts" / "clients" / "python"

    if not spec_path.exists():
        print(f"Error: OpenAPI spec not found at {spec_path}")
        sys.exit(1)

    # Ensure output directory exists
    output_dir.parent.mkdir(parents=True, exist_ok=True)

    # Generate the client (dependencies already installed by Makefile)
    print(f"Generating Python client from {spec_path}...")
    cmd = [
        "uv",
        "run",
        "--active",
        "openapi-python-client",
        "generate",
        "--path",
        str(spec_path),
        "--output-path",
        str(output_dir),
        "--overwrite",
    ]

    result = subprocess.run(cmd, capture_output=True, text=True, cwd=project_dir)

    if result.returncode != 0:
        print(f"Error generating client: {result.stderr}")
        sys.exit(1)

    print(f"Successfully generated Python client in {output_dir}")
    print(result.stdout)


if __name__ == "__main__":
    generate_python_client()
