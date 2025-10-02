from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlmodel import SQLModel
from policyengine_fastapi.exit import exit
from .settings import get_settings
import logging
import dotenv
dotenv.load_dotenv()

# Import routers
from .routers import (
    models,
    policies,
    simulations,
    datasets,
    parameters,
    dynamics,
    model_versions,
    baseline_variables,
    reports,
    report_elements,
    aggregates,
    aggregate_changes,
    data_requests,
    users,
    user_simulations,
    user_policies,
    user_datasets,
)

# Import database setup
from .database import engine

# Import all tables to ensure they're registered with SQLModel
from policyengine.database import (
    ModelTable,
    PolicyTable,
    SimulationTable,
    DatasetTable,
    VersionedDatasetTable,
    ParameterTable,
    ParameterValueTable,
    BaselineParameterValueTable,
    BaselineVariableTable,
    DynamicTable,
    ModelVersionTable,
    ReportTable,
    ReportElementTable,
    AggregateTable,
    AggregateChangeTable,
    UserTable,
    UserPolicyTable,
    UserDynamicTable,
    UserDatasetTable,
    UserSimulationTable,
    UserReportTable,
)

"""
specific example instantiation of the app configured by a .env file
* Uses Supabase PostgreSQL database
* on desktop we print opentelemetry instrumentation to the console.
* in "production" we use GCP trace/metrics bindings.
"""

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Create tables on startup
    SQLModel.metadata.create_all(engine)
    yield


app = FastAPI(
    title="policyengine-api-full",
    summary="External facing policyengineAPI containing all features",
    lifespan=lifespan
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:5174"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(models.router)
app.include_router(policies.router)
app.include_router(simulations.router)
app.include_router(datasets.datasets_router)
app.include_router(datasets.versioned_datasets_router)
app.include_router(parameters.parameters_router)
app.include_router(parameters.parameter_values_router)
app.include_router(parameters.baseline_parameter_values_router)
app.include_router(dynamics.router)
app.include_router(model_versions.router)
app.include_router(baseline_variables.router)
app.include_router(reports.reports_router)
app.include_router(report_elements.report_elements_router)
app.include_router(aggregates.aggregates_router)
app.include_router(aggregate_changes.aggregate_changes_router)
app.include_router(data_requests.router)
app.include_router(users.router)
app.include_router(user_simulations.router)
app.include_router(user_policies.router)
app.include_router(user_datasets.router)

# Health check endpoint
@app.get("/health")
def health_check():
    """Health check endpoint."""
    return {"status": "healthy"}
