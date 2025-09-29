#!/usr/bin/env python3
"""
Simple database initialization script for PolicyEngine API.
Creates initial data without running full simulations.
"""

import os
from datetime import datetime
from policyengine.database import Database
from policyengine.models import (
    Parameter,
    ParameterValue,
    Policy,
    policyengine_uk_latest_version,
    policyengine_uk_model,
)


def init_database_simple(database_url: str = None):
    """
    Initialize the database with models and sample data.

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

    try:
        # Register model versions (this is fast)
        print("Registering UK model version...")
        database.register_model_version(policyengine_uk_latest_version)
        print("✓ UK model registered")

        # Create a sample UK policy
        print("Creating sample UK policy...")
        personal_allowance = Parameter(
            id="gov.hmrc.income_tax.allowances.personal_allowance.amount",
            model=policyengine_uk_model,
        )

        personal_allowance_value = ParameterValue(
            parameter=personal_allowance,
            start_date=datetime(2024, 4, 1),
            value=20000,
        )

        uk_policy = Policy(
            name="Increase personal allowance to £20,000",
            description="A policy to increase the personal allowance for income tax to £20,000.",
            parameter_values=[personal_allowance_value],
        )

        database.set(uk_policy)
        for pv in uk_policy.parameter_values:
            database.set(pv)
        print("✓ Sample policy created")

        print("\n✓ Database initialization complete!")
        print("Note: To create simulations and aggregates, use the API endpoints.")

    except Exception as e:
        print(f"\n✗ Error during initialization: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Initialize PolicyEngine database (simple)")
    parser.add_argument(
        "--database-url",
        help="PostgreSQL connection string",
        default="postgresql://postgres:postgres@127.0.0.1:54322/postgres"
    )

    args = parser.parse_args()

    init_database_simple(database_url=args.database_url)