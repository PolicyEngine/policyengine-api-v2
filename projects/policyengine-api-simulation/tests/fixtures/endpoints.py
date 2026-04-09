"""
Fixtures for gateway endpoints tests.

Provides mocks for Modal Dict and Function classes.
"""

import pytest


class MockDict:
    """Mock for Modal.Dict to simulate version registry."""

    def __init__(self, data: dict):
        self._data = data

    def __getitem__(self, key: str):
        if key not in self._data:
            raise KeyError(key)
        return self._data[key]

    def __setitem__(self, key: str, value):
        self._data[key] = value

    def get(self, key: str, default=None):
        return self._data.get(key, default)

    @classmethod
    def from_name(cls, name: str):
        """Mock from_name that returns a MockDict based on name."""
        # This will be overridden in tests
        raise NotImplementedError("Mock not configured")


class MockFunctionCall:
    """Mock for Modal FunctionCall returned by spawn."""

    def __init__(
        self,
        object_id: str = "mock-job-id-123",
        result: dict | None = None,
        error: Exception | None = None,
        is_running: bool = False,
    ):
        self.object_id = object_id
        self._result = result
        self._error = error
        self._is_running = is_running

    def get(self, timeout: int = 0):
        if self._is_running:
            raise TimeoutError()
        if self._error is not None:
            raise self._error
        return self._result


class MockFunction:
    """Mock for Modal Function."""

    def __init__(self):
        self.last_payload = None
        self.last_from_name_call = None
        self.last_call = MockFunctionCall()

    def spawn(self, payload: dict) -> MockFunctionCall:
        self.last_payload = payload
        self.last_call = MockFunctionCall()
        return self.last_call

    @classmethod
    def from_name(cls, app_name: str, func_name: str):
        """Mock from_name that returns a MockFunction."""
        # This will be overridden in tests
        raise NotImplementedError("Mock not configured")


@pytest.fixture
def mock_modal(monkeypatch):
    """
    Fixture that patches the modal library calls in the endpoints module.

    Returns a dict with mock objects that tests can configure.

    Note: pytest's pythonpath config adds 'src' to path, causing 'import modal'
    to find our local src/modal package. We patch at the module level in endpoints.

    Usage:
        def test_something(mock_modal, client):
            mock_modal["dicts"]["simulation-api-us-versions"] = {
                "latest": "1.500.0",
                "1.500.0": "policyengine-simulation-us1-500-0-uk2-66-0",
            }
            # ... test code ...
    """
    from src.modal.gateway import endpoints

    # Create mock objects
    mock_func = MockFunction()
    mock_dicts = {}
    function_calls = {}

    class MockModalDict:
        @staticmethod
        def from_name(name: str, **kwargs):
            if name not in mock_dicts:
                if kwargs.get("create_if_missing"):
                    mock_dicts[name] = {}
                else:
                    raise KeyError(f"Mock dict not configured for: {name}")
            if name not in mock_dicts:
                raise KeyError(f"Mock dict not configured for: {name}")
            return MockDict(mock_dicts[name])

    class MockModalFunction:
        @staticmethod
        def from_name(app_name: str, func_name: str):
            mock_func.last_from_name_call = (app_name, func_name)
            return mock_func

    class MockModalFunctionCall:
        @staticmethod
        def from_id(job_id: str):
            if job_id not in function_calls:
                raise KeyError(job_id)
            return function_calls[job_id]

    # Create a mock modal module object
    class MockModal:
        Dict = MockModalDict
        Function = MockModalFunction
        FunctionCall = MockModalFunctionCall

    # Patch the modal import in the endpoints module
    monkeypatch.setattr(endpoints, "modal", MockModal)

    return {
        "func": mock_func,
        "dicts": mock_dicts,
        "function_calls": function_calls,
    }
