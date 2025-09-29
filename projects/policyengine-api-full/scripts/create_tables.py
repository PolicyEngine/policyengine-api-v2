#!/usr/bin/env python3
"""
Create database tables for PolicyEngine API.
"""

import os
from policyengine.database import Database
from sqlmodel import SQLModel

def create_tables(database_url: str = None):
    """
    Create all database tables.

    Args:
        database_url: PostgreSQL connection string. If None, uses DATABASE_URL env var
    """
    # Get database URL
    if database_url is None:
        database_url = os.environ.get(
            "DATABASE_URL",
            "postgresql://postgres:postgres@127.0.0.1:54322/postgres"
        )

    print(f"Connecting to database: {database_url}")
    database = Database(database_url)

    print("Creating all tables...")
    # This will create all tables defined in SQLModel
    SQLModel.metadata.create_all(database.engine)

    print("Tables created successfully!")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Create PolicyEngine database tables")
    parser.add_argument(
        "--database-url",
        help="PostgreSQL connection string",
        default="postgresql://postgres:postgres@127.0.0.1:54322/postgres"
    )

    args = parser.parse_args()

    create_tables(database_url=args.database_url)