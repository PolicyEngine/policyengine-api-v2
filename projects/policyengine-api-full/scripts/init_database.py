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

    # Create baseline simulations
    print("Creating UK baseline simulation...")
    uk_baseline = Simulation(
        dataset=uk_dataset,
        model=policyengine_uk_model,
        model_version=policyengine_uk_latest_version,
        label="UK Baseline 2024"
    )
    uk_baseline.run()
    database.set(uk_baseline)

    # Create sample UK policy reform
    print("Creating UK sample policy...")
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

    # Create UK reform simulation
    print("Creating UK reform simulation...")
    uk_reform = Simulation(
        dataset=uk_dataset,
        model=policyengine_uk_model,
        model_version=policyengine_uk_latest_version,
        policy=uk_policy,
        label="UK Reform: £20k Personal Allowance"
    )
    uk_reform.run()
    database.set(uk_reform)

    # Create sample aggregates for UK
    print("Creating UK sample aggregates...")
    income_ranges = [0, 20000, 40000, 60000, 80000, 100000]

    uk_aggregates = []
    for i in range(len(income_ranges) - 1):
        # Baseline aggregate
        agg = Aggregate(
            entity="household",
            variable_name="household_net_income",
            aggregate_function="count",
            filter_variable_name="household_net_income",
            filter_variable_geq=income_ranges[i],
            filter_variable_leq=income_ranges[i + 1],
            simulation=uk_baseline,
        )
        uk_aggregates.append(agg)

        # Reform aggregate
        agg_reform = Aggregate(
            entity="household",
            variable_name="household_net_income",
            aggregate_function="count",
            filter_variable_name="household_net_income",
            filter_variable_geq=income_ranges[i],
            filter_variable_leq=income_ranges[i + 1],
            simulation=uk_reform,
        )
        uk_aggregates.append(agg_reform)

    # Run aggregates
    uk_aggregates = Aggregate.run(uk_aggregates)
    for agg in uk_aggregates:
        database.set(agg)

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
        default=True,
        action="store_true",
        help="Reset (drop and recreate) all tables"
    )

    args = parser.parse_args()

    init_database(database_url=args.database_url, reset=args.reset)