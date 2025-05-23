#!/bin/bash

script_dir=$(dirname "$0")
cd ${script_dir}
poetry install &> /dev/null
poetry run python scripts/dump_package_version.py poetry.lock "$@"
