from sqlmodel import create_engine, Session
from sqlalchemy.pool import NullPool
import os
from typing import Generator
from policyengine.database import Database

database = Database(os.environ.get("DATABASE_URL", "postgresql://postgres:postgres@127.0.0.1:54322/postgres"))

engine = database.engine

def get_session() -> Generator[Session, None, None]:
    """Dependency to get database session."""
    with Session(engine) as session:
        yield session
