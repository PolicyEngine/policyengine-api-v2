"""Unit tests for Modal deployment bash scripts.

These tests verify the bash scripts in .github/scripts/ work correctly.
Tests use subprocess to invoke the scripts and verify their behavior.
"""

import os
import subprocess
import tempfile
from pathlib import Path

import pytest

# Path to the repository root
REPO_ROOT = Path(__file__).parent.parent.parent.parent
SCRIPTS_DIR = REPO_ROOT / ".github" / "scripts"


@pytest.fixture
def temp_github_output():
    """Create a temporary file to simulate GITHUB_OUTPUT."""
    with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".txt") as f:
        yield f.name
    os.unlink(f.name)


@pytest.fixture
def temp_github_step_summary():
    """Create a temporary file to simulate GITHUB_STEP_SUMMARY."""
    with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".md") as f:
        yield f.name
    os.unlink(f.name)


class TestModalExtractVersions:
    """Tests for modal-extract-versions.sh"""

    script = SCRIPTS_DIR / "modal-extract-versions.sh"

    def test_script_exists(self):
        """Script file should exist."""
        assert self.script.exists(), f"Script not found at {self.script}"

    def test_script_is_executable_or_can_be_run_with_bash(self):
        """Script should be runnable with bash."""
        result = subprocess.run(
            ["bash", "-n", str(self.script)],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, f"Syntax error in script: {result.stderr}"

    def test_extracts_versions_from_uv_lock(self, temp_github_output):
        """Should extract policyengine-us and policyengine-uk versions from uv.lock."""
        project_dir = REPO_ROOT / "projects" / "policyengine-api-simulation"

        if not (project_dir / "uv.lock").exists():
            pytest.skip("uv.lock not found in project directory")

        env = os.environ.copy()
        env["GITHUB_OUTPUT"] = temp_github_output

        result = subprocess.run(
            ["bash", str(self.script), str(project_dir)],
            capture_output=True,
            text=True,
            env=env,
        )

        assert result.returncode == 0, f"Script failed: {result.stderr}"

        with open(temp_github_output) as f:
            output = f.read()

        assert "us_version=" in output, "us_version not found in output"
        assert "uk_version=" in output, "uk_version not found in output"


class TestModalHealthCheck:
    """Tests for modal-health-check.sh"""

    script = SCRIPTS_DIR / "modal-health-check.sh"

    def test_script_exists(self):
        """Script file should exist."""
        assert self.script.exists(), f"Script not found at {self.script}"

    def test_script_syntax(self):
        """Script should have valid bash syntax."""
        result = subprocess.run(
            ["bash", "-n", str(self.script)],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, f"Syntax error: {result.stderr}"

    def test_requires_base_url_argument(self):
        """Should fail when no URL is provided."""
        result = subprocess.run(
            ["bash", str(self.script)],
            capture_output=True,
            text=True,
        )
        assert result.returncode != 0, "Should fail without URL argument"

    def test_fails_on_unreachable_url(self):
        """Should fail when URL is unreachable."""
        result = subprocess.run(
            ["bash", str(self.script), "http://localhost:99999/nonexistent", "1", "1"],
            capture_output=True,
            text=True,
        )
        assert result.returncode != 0, "Should fail on unreachable URL"


class TestModalDeploymentSummary:
    """Tests for modal-deployment-summary.sh"""

    script = SCRIPTS_DIR / "modal-deployment-summary.sh"

    def test_script_exists(self):
        """Script file should exist."""
        assert self.script.exists(), f"Script not found at {self.script}"

    def test_script_syntax(self):
        """Script should have valid bash syntax."""
        result = subprocess.run(
            ["bash", "-n", str(self.script)],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, f"Syntax error: {result.stderr}"

    def test_generates_success_summary(self, temp_github_step_summary):
        """Should generate markdown summary for successful deployments."""
        env = os.environ.copy()
        env["GITHUB_STEP_SUMMARY"] = temp_github_step_summary

        result = subprocess.run(
            [
                "bash",
                str(self.script),
                "success",
                "https://beta.example.com",
                "success",
                "https://prod.example.com",
            ],
            capture_output=True,
            text=True,
            env=env,
        )

        assert result.returncode == 0, f"Script failed: {result.stderr}"

        with open(temp_github_step_summary) as f:
            summary = f.read()

        assert "Modal Deployment Summary" in summary
        assert "Beta deployment" in summary
        assert "Production deployment" in summary
        assert "https://beta.example.com" in summary
        assert "https://prod.example.com" in summary

    def test_generates_skipped_summary(self, temp_github_step_summary):
        """Should handle skipped deployments."""
        env = os.environ.copy()
        env["GITHUB_STEP_SUMMARY"] = temp_github_step_summary

        result = subprocess.run(
            [
                "bash",
                str(self.script),
                "skipped",
                "",
                "success",
                "https://prod.example.com",
            ],
            capture_output=True,
            text=True,
            env=env,
        )

        assert result.returncode == 0

        with open(temp_github_step_summary) as f:
            summary = f.read()

        assert "Beta deployment" in summary


class TestModalSyncSecrets:
    """Tests for modal-sync-secrets.sh"""

    script = SCRIPTS_DIR / "modal-sync-secrets.sh"

    def test_script_exists(self):
        """Script file should exist."""
        assert self.script.exists(), f"Script not found at {self.script}"

    def test_script_syntax(self):
        """Script should have valid bash syntax."""
        result = subprocess.run(
            ["bash", "-n", str(self.script)],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, f"Syntax error: {result.stderr}"

    def test_requires_modal_environment_argument(self):
        """Should fail when no modal environment is provided."""
        result = subprocess.run(
            ["bash", str(self.script)],
            capture_output=True,
            text=True,
        )
        assert result.returncode != 0, "Should fail without modal environment"

    def test_requires_gh_environment_argument(self):
        """Should fail when no GH environment is provided."""
        result = subprocess.run(
            ["bash", str(self.script), "staging"],
            capture_output=True,
            text=True,
        )
        assert result.returncode != 0, "Should fail without GH environment"


class TestModalDeployApp:
    """Tests for modal-deploy-app.sh"""

    script = SCRIPTS_DIR / "modal-deploy-app.sh"

    def test_script_exists(self):
        """Script file should exist."""
        assert self.script.exists(), f"Script not found at {self.script}"

    def test_script_syntax(self):
        """Script should have valid bash syntax."""
        result = subprocess.run(
            ["bash", "-n", str(self.script)],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, f"Syntax error: {result.stderr}"

    def test_requires_modal_environment_argument(self):
        """Should fail when no modal environment is provided."""
        result = subprocess.run(
            ["bash", str(self.script)],
            capture_output=True,
            text=True,
        )
        assert result.returncode != 0, "Should fail without modal environment"


class TestModalGetUrl:
    """Tests for modal-get-url.sh"""

    script = SCRIPTS_DIR / "modal-get-url.sh"

    def test_script_exists(self):
        """Script file should exist."""
        assert self.script.exists(), f"Script not found at {self.script}"

    def test_script_syntax(self):
        """Script should have valid bash syntax."""
        result = subprocess.run(
            ["bash", "-n", str(self.script)],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, f"Syntax error: {result.stderr}"

    def test_requires_modal_environment_argument(self):
        """Should fail when no modal environment is provided."""
        result = subprocess.run(
            ["bash", str(self.script)],
            capture_output=True,
            text=True,
        )
        assert result.returncode != 0, "Should fail without modal environment"


class TestModalSetupEnvironments:
    """Tests for modal-setup-environments.sh"""

    script = SCRIPTS_DIR / "modal-setup-environments.sh"

    def test_script_exists(self):
        """Script file should exist."""
        assert self.script.exists(), f"Script not found at {self.script}"

    def test_script_syntax(self):
        """Script should have valid bash syntax."""
        result = subprocess.run(
            ["bash", "-n", str(self.script)],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, f"Syntax error: {result.stderr}"


class TestModalRunIntegTests:
    """Tests for modal-run-integ-tests.sh"""

    script = SCRIPTS_DIR / "modal-run-integ-tests.sh"

    def test_script_exists(self):
        """Script file should exist."""
        assert self.script.exists(), f"Script not found at {self.script}"

    def test_script_syntax(self):
        """Script should have valid bash syntax."""
        result = subprocess.run(
            ["bash", "-n", str(self.script)],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, f"Syntax error: {result.stderr}"

    def test_requires_environment_argument(self):
        """Should fail when no environment is provided."""
        result = subprocess.run(
            ["bash", str(self.script)],
            capture_output=True,
            text=True,
        )
        assert result.returncode != 0, "Should fail without environment"

    def test_requires_base_url_argument(self):
        """Should fail when no base URL is provided."""
        result = subprocess.run(
            ["bash", str(self.script), "beta"],
            capture_output=True,
            text=True,
        )
        assert result.returncode != 0, "Should fail without base URL"


class TestAllScriptsHaveShebang:
    """Verify all scripts have proper shebang and error handling."""

    @pytest.fixture
    def all_modal_scripts(self):
        """Get all modal-*.sh scripts."""
        return list(SCRIPTS_DIR.glob("modal-*.sh"))

    def test_all_scripts_have_shebang(self, all_modal_scripts):
        """All scripts should start with #!/bin/bash."""
        for script in all_modal_scripts:
            with open(script) as f:
                first_line = f.readline().strip()
            assert first_line == "#!/bin/bash", f"{script.name} missing shebang"

    def test_all_scripts_have_strict_mode(self, all_modal_scripts):
        """All scripts should use set -euo pipefail for safety."""
        for script in all_modal_scripts:
            content = script.read_text()
            assert "set -euo pipefail" in content, f"{script.name} missing strict mode"

    def test_all_scripts_have_valid_syntax(self, all_modal_scripts):
        """All scripts should pass bash syntax check."""
        for script in all_modal_scripts:
            result = subprocess.run(
                ["bash", "-n", str(script)],
                capture_output=True,
                text=True,
            )
            assert result.returncode == 0, (
                f"{script.name} has syntax errors: {result.stderr}"
            )
