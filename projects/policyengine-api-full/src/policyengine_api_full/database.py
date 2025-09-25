from sqlmodel import create_engine, Session
from sqlalchemy.pool import NullPool
import os
from typing import Generator

def get_supabase_url() -> str:
    """Get Supabase database URL from environment or localhost."""
    # Default to local Supabase instance
    db_host = os.getenv("SUPABASE_DB_HOST", "localhost")
    db_port = os.getenv("SUPABASE_DB_PORT", "54322")
    db_name = os.getenv("SUPABASE_DB_NAME", "postgres")
    db_user = os.getenv("SUPABASE_DB_USER", "postgres")
    db_password = os.getenv("SUPABASE_DB_PASSWORD", "postgres")

    return f"postgresql://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}"

def create_supabase_engine():
    """Create SQLModel engine for Supabase PostgreSQL."""
    database_url = get_supabase_url()
    # Use NullPool to avoid connection pooling issues with serverless
    engine = create_engine(
        database_url,
        poolclass=NullPool,
        echo=os.getenv("SQL_ECHO", "false").lower() == "true"
    )
    return engine

def get_session() -> Generator[Session, None, None]:
    """Dependency to get database session."""
    engine = create_supabase_engine()
    with Session(engine) as session:
        yield session