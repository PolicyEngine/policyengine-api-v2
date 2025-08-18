#!/usr/bin/env python3
"""Ensure rich is installed before running make_helper.py"""

import subprocess
import sys

try:
    import rich
except ImportError:
    print("Installing rich...")
    subprocess.check_call(["uv", "pip", "install", "rich"])
