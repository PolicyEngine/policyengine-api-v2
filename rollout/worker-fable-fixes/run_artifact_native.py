from pathlib import Path
import sys

original = Path(
    "/Users/maxghenis/spm-rebuild-20260908/rollout/year-boundary-qualification/run_installed_native_qualification.py"
)
namespace = {"__file__": str(original), "__name__": "artifact_regression"}
exec(
    compile(original.read_text().split("import pytest\n", 1)[0], str(original), "exec"),
    namespace,
)
import pytest

raise SystemExit(pytest.main(sys.argv[1:]))
