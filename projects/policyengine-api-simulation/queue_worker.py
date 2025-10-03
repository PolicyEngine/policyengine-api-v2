#!/usr/bin/env python3
"""
Local development queue worker for processing simulations.

This script mimics the Google Cloud Workflow behaviour in production by:
1. Polling the database for simulations without results
2. Calling the simulation API to process them
3. Running continuously with a configurable polling interval

Usage:
    python queue_worker.py [--interval SECONDS] [--api-url URL]
"""
import os
import time
import logging
import argparse
import httpx
from policyengine.database import Database
from policyengine.models import Simulation
from sqlalchemy import select

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def process_pending_items(database: Database, api_url: str):
    """Find and process simulations, aggregates, and aggregate changes that don't have results yet."""
    total_processed = 0

    try:
        from policyengine.database import SimulationTable, AggregateTable, AggregateChangeTable

        # Process simulations
        stmt = select(SimulationTable.id).where(SimulationTable.result == None)
        # Use scalars() to get values directly instead of tuples
        pending_simulation_ids = list(database.session.exec(stmt).scalars())

        if pending_simulation_ids:
            logger.info(f"Found {len(pending_simulation_ids)} pending simulation(s)")

            for simulation_id in pending_simulation_ids:
                logger.info(f"Processing simulation {simulation_id}")

                try:
                    response = httpx.post(
                        f"{api_url}/run_simulation_sync/{simulation_id}",
                        timeout=1800.0
                    )

                    if response.status_code == 200:
                        logger.info(f"Successfully processed simulation {simulation_id}")
                        total_processed += 1
                    else:
                        logger.error(f"Failed to process simulation {simulation_id}: {response.status_code} - {response.text}")

                except httpx.TimeoutException:
                    logger.error(f"Timeout processing simulation {simulation_id}")
                except Exception as e:
                    logger.error(f"Error processing simulation {simulation_id}: {e}")

        # Process aggregates
        stmt = select(AggregateTable.id).where(AggregateTable.value == None)
        aggregate_ids = list(database.session.exec(stmt).scalars())

        if aggregate_ids:
            logger.info(f"Found {len(aggregate_ids)} pending aggregate(s)")

            try:
                response = httpx.post(
                    f"{api_url}/process_aggregates",
                    json=aggregate_ids,
                    timeout=1800.0
                )

                if response.status_code == 200:
                    logger.info(f"Successfully processed {len(aggregate_ids)} aggregates")
                    total_processed += len(aggregate_ids)
                else:
                    logger.error(f"Failed to process aggregates: {response.status_code} - {response.text}")

            except httpx.TimeoutException:
                logger.error(f"Timeout processing aggregates")
            except Exception as e:
                logger.error(f"Error processing aggregates: {e}")

        # Process aggregate changes
        stmt = select(AggregateChangeTable.id).where(AggregateChangeTable.change == None)
        change_ids = list(database.session.exec(stmt).scalars())

        if change_ids:
            logger.info(f"Found {len(change_ids)} pending aggregate change(s)")

            try:
                response = httpx.post(
                    f"{api_url}/process_aggregate_changes",
                    json=change_ids,
                    timeout=1800.0
                )

                if response.status_code == 200:
                    logger.info(f"Successfully processed {len(change_ids)} aggregate changes")
                    total_processed += len(change_ids)
                else:
                    logger.error(f"Failed to process aggregate changes: {response.status_code} - {response.text}")

            except httpx.TimeoutException:
                logger.error(f"Timeout processing aggregate changes")
            except Exception as e:
                logger.error(f"Error processing aggregate changes: {e}")

        if total_processed == 0:
            logger.debug("No pending items found")

        return total_processed

    except Exception as e:
        logger.error(f"Error querying for pending items: {e}")
        import traceback
        traceback.print_exc()
        return 0


def main():
    parser = argparse.ArgumentParser(description='Queue worker for processing simulations')
    parser.add_argument(
        '--interval',
        type=int,
        default=5,
        help='Polling interval in seconds (default: 5)'
    )
    parser.add_argument(
        '--api-url',
        type=str,
        default='http://localhost:8001',
        help='Simulation API base URL (default: http://localhost:8001)'
    )
    parser.add_argument(
        '--database-url',
        type=str,
        default=None,
        help='Database URL (defaults to DATABASE_URL env var or local postgres)'
    )

    args = parser.parse_args()

    # Initialize database
    db_url = args.database_url or os.environ.get(
        "DATABASE_URL",
        "postgresql://postgres:postgres@127.0.0.1:54322/postgres"
    )
    database = Database(url=db_url)

    logger.info(f"Starting queue worker")
    logger.info(f"Database: {db_url}")
    logger.info(f"Simulation API: {args.api_url}")
    logger.info(f"Polling interval: {args.interval}s")

    # Main polling loop
    try:
        while True:
            processed = process_pending_items(database, args.api_url)

            if processed > 0:
                logger.info(f"Processed {processed} item(s), checking again in {args.interval}s")

            time.sleep(args.interval)

    except KeyboardInterrupt:
        logger.info("Queue worker stopped by user")
    except Exception as e:
        logger.error(f"Queue worker crashed: {e}")
        raise


if __name__ == "__main__":
    main()
