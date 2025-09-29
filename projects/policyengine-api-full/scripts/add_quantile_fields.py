#!/usr/bin/env python3
"""
Add quantile filter fields to aggregates and aggregate_changes tables.
"""

import os
from sqlmodel import Session, text
from policyengine.database import Database

def add_quantile_fields(database_url: str = None):
    """
    Add quantile filter fields to existing tables.

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

    with Session(database.engine) as session:
        # Add quantile fields to aggregates table
        print("Adding quantile fields to aggregates table...")
        try:
            session.exec(text("""
                ALTER TABLE aggregates
                ADD COLUMN IF NOT EXISTS filter_variable_quantile_leq DOUBLE PRECISION,
                ADD COLUMN IF NOT EXISTS filter_variable_quantile_geq DOUBLE PRECISION,
                ADD COLUMN IF NOT EXISTS filter_variable_quantile_value VARCHAR;
            """))
            session.commit()
            print("✓ Added quantile fields to aggregates table")
        except Exception as e:
            print(f"Error adding fields to aggregates: {e}")
            session.rollback()

        # Add quantile fields to aggregate_changes table
        print("Adding quantile fields to aggregate_changes table...")
        try:
            session.exec(text("""
                ALTER TABLE aggregate_changes
                ADD COLUMN IF NOT EXISTS filter_variable_quantile_leq DOUBLE PRECISION,
                ADD COLUMN IF NOT EXISTS filter_variable_quantile_geq DOUBLE PRECISION,
                ADD COLUMN IF NOT EXISTS filter_variable_quantile_value VARCHAR;
            """))
            session.commit()
            print("✓ Added quantile fields to aggregate_changes table")
        except Exception as e:
            print(f"Error adding fields to aggregate_changes: {e}")
            session.rollback()

    print("\nMigration complete!")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Add quantile fields to PolicyEngine database")
    parser.add_argument(
        "--database-url",
        help="PostgreSQL connection string",
        default="postgresql://postgres:postgres@127.0.0.1:54322/postgres"
    )

    args = parser.parse_args()

    add_quantile_fields(database_url=args.database_url)