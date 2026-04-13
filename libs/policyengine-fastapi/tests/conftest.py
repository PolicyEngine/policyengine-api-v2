import sys
from pathlib import Path

pytest_plugins = ("fixtures.ping.shared",)

library_root = Path(__file__).parent.parent
if str(library_root) not in sys.path:
    sys.path.insert(0, str(library_root))
