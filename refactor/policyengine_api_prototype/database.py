from sqlmodel import (
    Field,
    Session,
    SQLModel,
    create_engine,
    Column,
    JSON,
    TIMESTAMP,
)
from policyengine import SimulationOptions
from datetime import datetime
from dotenv import load_dotenv
from pathlib import Path
import os
from google.cloud.sql.connector import Connector

load_dotenv()


class Job(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    parameters: dict | None = Field(default=None, sa_column=Column(JSON))
    result: dict | None = Field(default=None, sa_column=Column(JSON))
    created_at: datetime = Field(
        default_factory=datetime.utcnow,
        sa_column=Column(TIMESTAMP, default=datetime.utcnow),
    )


def get_local_database_engine():
    engine = create_engine(Path(__file__).parent / "database.db")
    SQLModel.metadata.create_all(engine)
    return engine


def get_production_database_engine():
    connector = Connector()
    getconn = lambda: connector.connect(
        "policyengine-api-prototype:us-central1:policyengine-api-prototype-database",
        "pg8000",
        user="postgres",
        password="postgres",  # Obviously bad, just for testing
        db="postgres",
    )
    engine = create_engine(
        "postgresql+pg8000://",
        creator=getconn,
    )
    SQLModel.metadata.create_all(engine)
    return engine
