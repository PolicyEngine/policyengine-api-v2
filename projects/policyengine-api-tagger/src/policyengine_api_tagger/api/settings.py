from enum import Enum
from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Environment(Enum):
    DESKTOP = "desktop"
    PRODUCTION = "production"


class AppSettings(BaseSettings):
    environment: Environment = Environment.DESKTOP

    """
    The audience that any JWT bearer token must include in order to be accepted by the API
    """
    ot_service_name: str = "YOUR_OT_SERVICE_NAME"
    """
    service name used by opentelemetry when reporting trace information
    """
    ot_service_instance_id: str = "YOUR_OT_INSTANCE_ID"
    """
    instance id used by opentelemetry when reporting trace information
    """
    metadata_bucket_name: str = "PROVIDE_BUCKET_NAME"
    """
    bucket containing the service metadata information (i.e. revisions a models)
    """

    # Cleanup configuration
    simulation_service_name: str = ""
    """
    Name of the simulation API Cloud Run service (e.g., 'api-simulation').
    Required for cleanup functionality.
    """
    project_id: str = ""
    """
    GCP project ID. Required for cleanup functionality.
    """
    region: str = ""
    """
    GCP region (e.g., 'us-central1'). Required for cleanup functionality.
    """

    model_config = SettingsConfigDict(env_file=".env")

    def cleanup_enabled(self) -> bool:
        """Check if cleanup functionality is properly configured."""
        return bool(self.simulation_service_name and self.project_id and self.region)


@lru_cache
def get_settings():
    return AppSettings()
