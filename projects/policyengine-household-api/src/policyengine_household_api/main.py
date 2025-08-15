from fastapi import FastAPI
from policyengine_household_api.settings import get_settings, Environment
from policyengine_api.fastapi.opentelemetry import (
    GCPLoggingInstrumentor,
    FastAPIEnhancedInstrumenter,
    export_ot_to_console,
    export_ot_to_gcp,
)
from opentelemetry.sdk.resources import (
    SERVICE_NAME,
    SERVICE_INSTANCE_ID,
    Resource,
)
from policyengine_api.api.routers import (
    calculate,
    metadata,
)
from policyengine_api.api import initialize
import logging

"""
specific example instantiation of the app configured by a .env file
* in all environments we use sqlite
* on desktop we print opentelemetry instrumentation to the console.
* in "production" we use GCP trace/metrics bindings.
"""

logger = logging.getLogger(__name__)

app = FastAPI()

app.include_router(calculate.router)
app.include_router(metadata.router)

# attach the api defined in the app package
initialize(
    app=app,
    engine=None,  # type: ignore
    jwt_issuer=get_settings().jwt_issuer,
    jwt_audience=get_settings().jwt_audience,
)

# configure tracing and metrics
GCPLoggingInstrumentor().instrument()
FastAPIEnhancedInstrumenter().instrument(app)

resource = Resource.create(
    attributes={
        SERVICE_NAME: get_settings().ot_service_name,
        SERVICE_INSTANCE_ID: get_settings().ot_service_instance_id,
    }
)

match (get_settings().environment):
    case Environment.DESKTOP:
        pass# export_ot_to_console(resource)
    case Environment.PRODUCTION:
        export_ot_to_gcp(resource)
    case value:
        raise Exception(f"Forgot to handle environment value {value}")
