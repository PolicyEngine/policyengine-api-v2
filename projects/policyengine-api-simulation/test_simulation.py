#!/usr/bin/env python3
"""
Test script for the simulation API.
This demonstrates how to use the API endpoints that follow the pattern from test.py.
"""

import requests
import json
import time

# API base URL - adjust port as needed
BASE_URL = "http://localhost:8000"

def run_simulation_async(simulation_id: str):
    """Run a simulation asynchronously."""
    print(f"Running simulation {simulation_id} asynchronously...")

    response = requests.post(
        f"{BASE_URL}/run_simulation",
        json={"simulation_id": simulation_id}
    )

    if response.status_code == 200:
        result = response.json()
        print(f"Response: {result}")
        return result
    else:
        print(f"Error: {response.status_code} - {response.text}")
        return None


def run_simulation_sync(simulation_id: str):
    """Run a simulation synchronously."""
    print(f"Running simulation {simulation_id} synchronously...")

    response = requests.post(
        f"{BASE_URL}/run_simulation_sync/{simulation_id}"
    )

    if response.status_code == 200:
        result = response.json()
        print(f"Response: {result}")
        return result
    else:
        print(f"Error: {response.status_code} - {response.text}")
        return None


def check_simulation_status(simulation_id: str):
    """Check the status of a simulation."""
    print(f"Checking status of simulation {simulation_id}...")

    response = requests.get(
        f"{BASE_URL}/simulation/{simulation_id}/status"
    )

    if response.status_code == 200:
        result = response.json()
        print(f"Status: {result}")
        return result
    else:
        print(f"Error: {response.status_code} - {response.text}")
        return None


def main():
    # Example simulation ID - replace with an actual ID from your database
    simulation_id = "acc3eb26-fd1a-4477-9ce2-40e45855042f"

    print("=" * 50)
    print("Testing Simulation API")
    print("=" * 50)

    # Test 1: Run simulation synchronously (blocking)
    print("\n1. Running simulation synchronously (blocking):")
    run_simulation_sync(simulation_id)

    # Test 2: Check simulation status
    print("\n2. Checking simulation status:")
    check_simulation_status(simulation_id)

    # Test 3: Run simulation asynchronously
    print("\n3. Running simulation asynchronously:")
    result = run_simulation_async(simulation_id)

    if result:
        # Wait a bit then check status
        print("\nWaiting 5 seconds for async simulation to complete...")
        time.sleep(5)
        check_simulation_status(simulation_id)


if __name__ == "__main__":
    main()