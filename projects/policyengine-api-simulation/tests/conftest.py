"""Root pytest configuration for simulation API tests.

This conftest adds the project root to sys.path so that
imports like 'from src.modal.gateway.models import ...'
work correctly in tests. This matches how Modal's
.add_local_python_source("src.modal", copy=True) works at runtime.
"""

import sys
from pathlib import Path

# Add project root to sys.path so 'src.modal' imports work
project_root = Path(__file__).parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))
