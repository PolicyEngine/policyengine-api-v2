from contextlib import asynccontextmanager
from typing import Any
from fastapi import FastAPI
from .settings import get_settings, Environment
from policyengine_fastapi.opentelemetry import (
    GCPLoggingInstrumentor,
    FastAPIEnhancedInstrumenter,
    export_ot_to_console,
    export_ot_to_gcp,
)
from policyengine_fastapi.exit import exit
from opentelemetry.sdk.resources import (
    SERVICE_NAME,
    SERVICE_INSTANCE_ID,
    Resource,
)
from policyengine_api_simulation import initialize
from policyengine_fastapi import ping
from policyengine_fastapi.health import (
    HealthRegistry,
    HealthSystemReporter,
)
import logging

"""
specific example instantiation of the app configured by a .env file
* in all environments we use sqlite
* on desktop we print opentelemetry instrumentation to the console.
* in "production" we use GCP trace/metrics bindings.
"""

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with exit.lifespan():
        yield


app = FastAPI(
    lifespan=lifespan,
    title="policyengine-api-simulation",
    summary="Policyengine simulation api",
)

# attach the api defined in the app package
initialize(app=app)

# attach ping routes
health_registry = HealthRegistry()
health_registry.register(HealthSystemReporter("general", {}))
ping.include_all_routers(app, health_registry)

# configure tracing and metrics
GCPLoggingInstrumentor().instrument()
FastAPIEnhancedInstrumenter().instrument(app)

resource = Resource.create(
    attributes={
        SERVICE_NAME: get_settings().ot_service_name,
        SERVICE_INSTANCE_ID: get_settings().ot_service_instance_id,
    }
)

match get_settings().environment:
    case Environment.DESKTOP:
        pass  # Don't print opentelemetry to console- this makes it impossible to read the logs. Alternatively, do by uncommenting this line.
        # export_ot_to_console(resource)
    case Environment.PRODUCTION:
        export_ot_to_gcp(resource)
    case value:
        raise Exception(f"Forgot to handle environment value {value}")
