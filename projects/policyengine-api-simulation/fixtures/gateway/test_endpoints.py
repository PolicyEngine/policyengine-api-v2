"""Fixtures for gateway endpoint tests."""

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
        self._result = {"budget": {"total": 1000000}} if result is None else result
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

    def __init__(self, function_calls: dict[str, MockFunctionCall]):
        self.last_payload = None
        self.last_from_name_call = None
        self.last_call = MockFunctionCall()
        self._function_calls = function_calls

    def spawn(self, payload: dict) -> MockFunctionCall:
        self.last_payload = payload
        self.last_call = MockFunctionCall()
        self._function_calls[self.last_call.object_id] = self.last_call
        return self.last_call

    @classmethod
    def from_name(cls, app_name: str, func_name: str):
        """Mock from_name that returns a MockFunction."""
        raise NotImplementedError("Mock not configured")


@pytest.fixture
def mock_modal(monkeypatch):
    """Patch Modal calls in the gateway endpoints module."""
    from src.modal.gateway import endpoints

    mock_dicts = {}
    function_calls = {}
    mock_func = MockFunction(function_calls)

    class MockModalDict:
        @staticmethod
        def from_name(name: str, create_if_missing: bool = False):
            if name not in mock_dicts:
                if create_if_missing:
                    mock_dicts[name] = {}
                else:
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

    class MockModal:
        Dict = MockModalDict
        Function = MockModalFunction
        FunctionCall = MockModalFunctionCall

    monkeypatch.setattr(endpoints, "modal", MockModal)

    return {
        "func": mock_func,
        "dicts": mock_dicts,
        "function_calls": function_calls,
    }
