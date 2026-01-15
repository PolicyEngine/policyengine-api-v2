"""
Fixtures for orchestration module tests.

Provides mocks for Modal function calls and simulation spawning.
"""

from unittest.mock import MagicMock


class MockFunctionCall:
    """Mock for Modal's FunctionCall object returned by spawn()."""

    def __init__(self, result: dict | Exception):
        self._result = result

    def get(self) -> dict:
        if isinstance(self._result, Exception):
            raise self._result
        return self._result


def create_mock_run_simulation(results: dict[str, dict | Exception]):
    """
    Create a mock run_simulation function that returns different results per region.

    Args:
        results: Dict mapping region strings to their results/exceptions.
                 e.g., {"us": {...}, "state/tx": {...}, "state/ca": Exception(...)}

    Returns:
        A MagicMock with a spawn method that returns MockFunctionCall objects.
    """
    mock_func = MagicMock()

    def spawn_side_effect(params: dict) -> MockFunctionCall:
        region = params.get("region", "")
        if region in results:
            return MockFunctionCall(results[region])
        raise KeyError(f"No mock result for region: {region}")

    mock_func.spawn = MagicMock(side_effect=spawn_side_effect)
    return mock_func
