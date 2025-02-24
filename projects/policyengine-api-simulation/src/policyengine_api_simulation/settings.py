from enum import Enum
from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict

class Environment(Enum):
    DESKTOP = "desktop"
    PRODUCTION = "production"
    
class AppSettings(BaseSettings):
    environment:Environment = Environment.DESKTOP
    ot_service_name:str = "YOUR_OT_SERVICE_NAME"
    '''
    service name used by opentelemetry when reporting trace information
    '''
    ot_service_instance_id:str = "YOUR_OT_INSTANCE_ID"
    '''
    instance id used by opentelemetry when reporting trace information
    '''
    
    model_config = SettingsConfigDict(env_file=".env")


@lru_cache
def get_settings():
    return AppSettings()