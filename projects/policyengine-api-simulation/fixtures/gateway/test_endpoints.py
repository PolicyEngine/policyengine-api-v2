"""Fixtures for gateway endpoint tests."""

import pytest

TEST_APP_RELEASE_BUNDLE = {
    "app_name": "policyengine-simulation-py4-10-0",
    "policyengine_version": "4.10.0",
    "us": {
        "model_version": "1.500.0",
        "data_version": "1.110.12",
        "default_dataset": "enhanced_cps_2024",
        "default_dataset_uri": "hf://policyengine/policyengine-us-data/enhanced_cps_2024.h5@1.110.12",
        "dataset_uris": {
            "enhanced_cps_2024": "hf://policyengine/policyengine-us-data/enhanced_cps_2024.h5@1.110.12",
            "cps_2023": "hf://policyengine/policyengine-us-data/cps_2023.h5@1.110.12",
            "pooled_3_year_cps_2023": "hf://policyengine/policyengine-us-data/pooled_3_year_cps_2023.h5@1.110.12",
        },
        "dataset_aliases": {
            "enhanced_cps": "enhanced_cps_2024",
            "enhanced_cps_2024": "enhanced_cps_2024",
            "cps": "cps_2023",
            "cps_2023": "cps_2023",
            "pooled_cps": "pooled_3_year_cps_2023",
            "pooled_3_year_cps_2023": "pooled_3_year_cps_2023",
        },
    },
    "uk": {
        "model_version": "2.66.0",
        "data_version": "1.40.3",
        "default_dataset": "enhanced_frs_2023_24",
        "default_dataset_uri": "hf://policyengine/policyengine-uk-data-private/enhanced_frs_2023_24.h5@1.40.3",
        "dataset_uris": {
            "enhanced_frs_2023_24": "hf://policyengine/policyengine-uk-data-private/enhanced_frs_2023_24.h5@1.40.3",
            "frs_2023_24": "hf://policyengine/policyengine-uk-data-private/frs_2023_24.h5@1.40.3",
        },
        "dataset_aliases": {
            "enhanced_frs": "enhanced_frs_2023_24",
            "enhanced_frs_2023_24": "enhanced_frs_2023_24",
            "frs": "frs_2023_24",
            "frs_2023_24": "frs_2023_24",
        },
    },
}

TEST_APP_NAMES = (
    "policyengine-simulation-py4-10-0",
    "policyengine-simulation-py3-9-0",
)


def resolve_test_dataset_uri(country: str, dataset: str | None) -> str | None:
    if dataset is None:
        return None
    if "://" in dataset:
        return dataset
    country_bundle = TEST_APP_RELEASE_BUNDLE[country]
    dataset_name, revision = (
        dataset.rsplit("@", maxsplit=1) if "@" in dataset else (dataset, None)
    )
    dataset_name = country_bundle["dataset_aliases"].get(dataset_name, dataset_name)
    dataset_uri = country_bundle["dataset_uris"].get(dataset_name, dataset_name)
    if revision is not None and dataset_uri == dataset_name:
        return dataset
    if revision is not None and dataset_uri.startswith("hf://"):
        dataset_uri = f"{dataset_uri.rsplit('@', maxsplit=1)[0]}@{revision}"
    return dataset_uri


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

    registry = {}
    from_id_errors = {}

    def __init__(self, object_id: str = "mock-job-id-123"):
        self.object_id = object_id
        self.result = {"budget": {"total": 1000000}}
        self.error = None
        self.running = False
        self.__class__.registry[object_id] = self

    def get(self, timeout: int = 0):
        if self.running:
            raise TimeoutError()
        if self.error is not None:
            raise self.error
        return self.result

    @classmethod
    def from_id(cls, object_id: str):
        if object_id in cls.from_id_errors:
            raise cls.from_id_errors[object_id]
        if object_id not in cls.registry:
            raise KeyError(object_id)
        return cls.registry[object_id]


class MockFunction:
    """Mock for Modal Function."""

    def __init__(self):
        self.last_payload = None
        self.last_from_name_call = None
        self.last_call = None
        self.calls = []

    def bind(self, app_name: str, func_name: str) -> "BoundMockFunction":
        return BoundMockFunction(self, app_name, func_name)

    def call_for(self, object_id: str) -> MockFunctionCall:
        call = MockFunctionCall(object_id=object_id)
        self.last_call = call
        return call


class BoundMockFunction:
    """Function handle returned by Modal.Function.from_name."""

    def __init__(self, recorder: MockFunction, app_name: str, func_name: str):
        self.recorder = recorder
        self.app_name = app_name
        self.func_name = func_name

    def spawn(self, payload: dict) -> MockFunctionCall:
        self.recorder.last_payload = payload
        is_batch = self.func_name == "run_budget_window_batch"
        object_id = "mock-batch-job-id-123" if is_batch else "mock-job-id-123"
        self.recorder.last_call = MockFunctionCall(object_id=object_id)
        if is_batch:
            self.recorder.last_call.running = True
        self.recorder.calls.append((self.app_name, self.func_name, payload, object_id))
        return self.recorder.last_call


class MockModalException:
    class NotFoundError(Exception):
        pass

    class OutputExpiredError(Exception):
        pass


@pytest.fixture
def mock_modal(monkeypatch):
    """Patch Modal calls in the gateway endpoints module."""
    from src.modal import budget_window_state
    from src.modal.gateway import endpoints

    mock_func = MockFunction()
    mock_dicts = {
        "simulation-api-app-release-bundles": {
            app_name: TEST_APP_RELEASE_BUNDLE for app_name in TEST_APP_NAMES
        }
    }
    MockFunctionCall.registry = {}
    MockFunctionCall.from_id_errors = {}

    class MockModalDict:
        @staticmethod
        def from_name(name: str, create_if_missing: bool = False):
            if create_if_missing and name not in mock_dicts:
                mock_dicts[name] = {}
            if name not in mock_dicts:
                raise KeyError(f"Mock dict not configured for: {name}")
            return MockDict(mock_dicts[name])

    class MockModalFunction:
        @staticmethod
        def from_name(app_name: str, func_name: str):
            mock_func.last_from_name_call = (app_name, func_name)
            return mock_func.bind(app_name, func_name)

    class MockModal:
        Dict = MockModalDict
        Function = MockModalFunction
        FunctionCall = MockFunctionCall
        exception = MockModalException

    monkeypatch.setattr(endpoints, "modal", MockModal)
    monkeypatch.setattr(budget_window_state, "modal", MockModal)
    monkeypatch.setattr(
        endpoints,
        "with_hf_revision",
        lambda dataset_uri, revision: (
            f"{dataset_uri.rsplit('@', maxsplit=1)[0]}@{revision}"
            if dataset_uri.startswith("hf://")
            else dataset_uri
        ),
    )
    monkeypatch.setattr(
        endpoints,
        "validate_hf_dataset_uri",
        lambda dataset_uri: dataset_uri,
    )

    return {
        "func": mock_func,
        "dicts": mock_dicts,
        "function_call": MockFunctionCall,
        "exception": MockModalException,
    }
