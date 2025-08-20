from contextlib import asynccontextmanager
from typing import Any
from fastapi import FastAPI
from policyengine_fastapi import ping
from policyengine_fastapi.health import (
    HealthRegistry,
    HealthSystemReporter,
)
from policyengine_fastapi.exit import exit

from .api.revision_tagger import RevisionTagger
from .api.routes import add_all_routes
from .api.settings import get_settings, Environment
from policyengine_fastapi.opentelemetry import (
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
import logging

"""
specific example instantiation of the app configured by a .env file
* in all environments we use sqlite
* on desktop we print opentelemetry instrumentation to the console.
* in "production" we use GCP trace/metrics bindings.
"""

logger = logging.getLogger(__name__)


app = FastAPI(
    title="policyengine-api-tagger",
    summary="Internal service that tags revisions of the simulation api",
)

tagger = RevisionTagger(get_settings().metadata_bucket_name)

add_all_routes(app, tagger)

health_registry = HealthRegistry()
# TODO: we can use this to verify the db connection, etc.
# For now, we don't register any probes and it will just report
# healthy all the time.
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
        pass  # export_ot_to_console(resource)
    case Environment.PRODUCTION:
        export_ot_to_gcp(resource)
    case value:
        raise Exception(f"Forgot to handle environment value {value}")
