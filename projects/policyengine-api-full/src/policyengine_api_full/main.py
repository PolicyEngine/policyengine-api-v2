from contextlib import asynccontextmanager
from typing import Any
from fastapi import FastAPI
from sqlmodel import SQLModel
from policyengine_api.fastapi.database import create_sqlite_engine
from policyengine_api.fastapi import ping
from policyengine_api.fastapi.health import HealthRegistry, HealthSystemReporter
from policyengine_api.fastapi.exit import exit
from .settings import get_settings, Environment
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
from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
from policyengine_api.api import initialize
import logging

"""
specific example instantiation of the app configured by a .env file
* in all environments we use sqlite
* on desktop we print opentelemetry instrumentation to the console.
* in "production" we use GCP trace/metrics bindings.
"""

logger = logging.getLogger(__name__)

# configure database
# manage tables directly from defined models.
engine = create_sqlite_engine()


@asynccontextmanager
async def lifespan(app: FastAPI):
    SQLModel.metadata.create_all(engine)
    async with exit.lifespan():
        yield


app = FastAPI(
    lifespan=lifespan,
    title="policyengine-api-full",
    summary="External facing policyengineAPI containing all features",
)

# attach the api defined in the app package
initialize(
    app=app,
    engine=engine,
    jwt_issuer=get_settings().jwt_issuer,
    jwt_audience=get_settings().jwt_audience,
)

health_registry = HealthRegistry()
#TODO: we can use this to verify the db connection, etc.
#For now, we don't register any probes and it will just report
# healthy all the time.
health_registry.register(HealthSystemReporter("general", {}))
ping.include_all_routers(app, health_registry)

# configure tracing and metrics
GCPLoggingInstrumentor().instrument()
FastAPIEnhancedInstrumenter().instrument(app)
SQLAlchemyInstrumentor().instrument(
    engine=engine, enable_commenter=True, commenter_options={}
)

resource = Resource.create(
    attributes={
        SERVICE_NAME: get_settings().ot_service_name,
        SERVICE_INSTANCE_ID: get_settings().ot_service_instance_id,
    }
)

match (get_settings().environment):
    case Environment.DESKTOP:
        export_ot_to_console(resource)
    case Environment.PRODUCTION:
        export_ot_to_gcp(resource)
    case value:
        raise Exception(f"Forgot to handle environment value {value}")
