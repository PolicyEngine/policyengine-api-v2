from sqlmodel import create_engine, Session, SQLModel
from sqlalchemy.pool import NullPool
import os
from typing import Generator
from policyengine.database import Database

database_url = os.environ.get("DATABASE_URL", "postgresql://postgres:postgres@127.0.0.1:54322/postgres")

# Create the core database instance
database = Database(database_url)
engine = database.engine

def create_api_tables():
    """Create API-specific tables (users, reports, associations) that extend the core schema."""
    from policyengine_api_full.models import (
        UserTable,
        ReportTable,
        ReportElementTable,
        UserPolicyTable,
        UserDatasetTable,
        UserSimulationTable,
        UserDynamicTable,
        UserReportTable,
    )

    # Create only the API-specific tables
    SQLModel.metadata.create_all(
        engine,
        tables=[
            UserTable.__table__,
            ReportTable.__table__,
            ReportElementTable.__table__,
            UserPolicyTable.__table__,
            UserDatasetTable.__table__,
            UserSimulationTable.__table__,
            UserDynamicTable.__table__,
            UserReportTable.__table__,
        ]
    )

def get_session() -> Generator[Session, None, None]:
    """Dependency to get database session."""
    with Session(engine) as session:
        yield session
