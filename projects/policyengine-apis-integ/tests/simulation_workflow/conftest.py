from pydantic_settings import BaseSettings, SettingsConfigDict
import pytest
from .simplified_workflow_client import SimplifiedWorkflowClient


class Settings(BaseSettings):
    project_id: str = "UNKNOWN_PROJECT_ID"
    location: str = "us-central1"
    workflow_id: str = "simulation-workflow"
    us_model_version: str = "UNKNOWN_US_MODEL_VERSION"

    model_config = SettingsConfigDict(env_prefix="workflow_integ_test_")


settings = Settings()


@pytest.fixture()
def us_model_version() -> str:
    return settings.us_model_version


@pytest.fixture()
def client() -> SimplifiedWorkflowClient:
    return SimplifiedWorkflowClient(
        settings.project_id, settings.location, settings.workflow_id
    )
