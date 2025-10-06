#!/usr/bin/env python3
"""
Migration script to add API-specific tables (users, reports, associations).

This script creates new tables without modifying existing ones.
It's safe to run multiple times (idempotent).
"""

import os
import sys
from sqlmodel import SQLModel
from policyengine.database import Database


def migrate_add_api_tables(database_url: str = None):
    """
    Add API-specific tables to existing database.

    This migration adds:
    - users
    - reports
    - report_elements
    - user_policies
    - user_datasets
    - user_simulations
    - user_dynamics
    - user_reports

    Args:
        database_url: PostgreSQL connection string
    """
    if database_url is None:
        database_url = os.environ.get(
            "DATABASE_URL",
            "postgresql://postgres:postgres@127.0.0.1:54322/postgres"
        )

    print(f"Connecting to database: {database_url}")
    database = Database(database_url)

    try:
        # Import API tables
        print("Importing API table definitions...")
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

        # Create only the new tables
        print("Creating API-specific tables...")
        SQLModel.metadata.create_all(
            database.engine,
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

        print("✓ API tables created successfully")

        # Create anonymous user if it doesn't exist
        print("Ensuring anonymous user exists...")
        from sqlmodel import select

        stmt = select(UserTable).where(UserTable.id == "anonymous")
        existing = database.session.exec(stmt).first()

        if not existing:
            anonymous_user = UserTable(
                id="anonymous",
                username="anonymous",
                first_name="Anonymous",
                last_name="User",
                email=None,
                current_model_id="policyengine_uk",
            )
            database.session.add(anonymous_user)
            database.session.commit()
            print("✓ Anonymous user created")
        else:
            print("✓ Anonymous user already exists")

        print("\n✓ Migration complete!")

    except Exception as e:
        print(f"\n✗ Migration failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Migrate: Add API-specific tables")
    parser.add_argument(
        "--database-url",
        help="PostgreSQL connection string",
        default="postgresql://postgres:postgres@127.0.0.1:54322/postgres"
    )

    args = parser.parse_args()
    migrate_add_api_tables(database_url=args.database_url)
