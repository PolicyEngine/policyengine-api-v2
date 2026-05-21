"""Static checks for the Modal deployment workflow release gates."""

from __future__ import annotations

from fixtures.test_modal_scripts import REPO_ROOT


WORKFLOW = REPO_ROOT / ".github" / "workflows" / "modal-deploy.yml"


def test_modal_deploy_workflow_uses_two_stage_release_commit() -> None:
    workflow = WORKFLOW.read_text(encoding="utf-8")

    assert "name: Update versioning" in workflow
    assert "github.event.head_commit.message == 'Update Simulation API'" in workflow
    assert "!(github.event.head_commit.message == 'Update Simulation API')" in workflow
    assert "message: Update Simulation API" in workflow


def test_modal_deploy_workflow_keeps_manual_dispatch_direct_deploy() -> None:
    workflow = WORKFLOW.read_text(encoding="utf-8")

    assert "workflow_dispatch:" in workflow
    assert "skip_beta:" in workflow
    assert "github.event_name == 'workflow_dispatch'" in workflow


def test_modal_deploy_workflow_publishes_simulation_api_tag() -> None:
    workflow = WORKFLOW.read_text(encoding="utf-8")

    assert "name: Publish simulation API tag" in workflow
    assert ".github/scripts/publish-simulation-api-tag.sh" in workflow
