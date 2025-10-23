#!/usr/bin/env python3
"""
Database initialization script for PolicyEngine API.
Creates initial data including models, simulations, and sample aggregates.
"""

import os
from datetime import datetime
from policyengine.database import Database
from policyengine.models import (
    Aggregate,
    Simulation,
    Parameter,
    ParameterValue,
    Policy,
    policyengine_uk_latest_version,
    policyengine_uk_model,
    policyengine_us_latest_version,
    policyengine_us_model,
)
from policyengine.utils.datasets import create_uk_dataset, create_us_dataset


def init_database(database_url: str = None, reset: bool = False):
    """
    Initialize the database with models and sample data.

    Args:
        database_url: PostgreSQL connection string. If None, uses DATABASE_URL env var
        reset: Whether to reset (drop and recreate) all tables
    """
    # Get database URL
    if database_url is None:
        database_url = os.environ.get(
            "DATABASE_URL",
            "postgresql://postgres:postgres@127.0.0.1:54322/postgres"
        )

    print(f"Connecting to database: {database_url}")
    database = Database(database_url)

    if reset:
        print("Resetting database tables...")
        database.reset()
    else:
        print("Creating database tables if they don't exist...")
        database.create_tables()

    # Register model versions
    print("Registering UK model version...")
    database.register_model_version(policyengine_uk_latest_version)

    # Create datasets
    print("Creating UK dataset...")
    uk_dataset = create_uk_dataset()
    database.set(uk_dataset)

    print("\nDatabase initialization complete!")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Initialize PolicyEngine database")
    parser.add_argument(
        "--database-url",
        help="PostgreSQL connection string",
        default=None
    )
    parser.add_argument(
        "--reset",
        default=False,
        action="store_true",
        help="Reset (drop and recreate) all tables"
    )

    args = parser.parse_args()

    init_database(database_url=args.database_url, reset=args.reset)