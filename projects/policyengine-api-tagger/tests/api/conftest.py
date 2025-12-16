from unittest.mock import AsyncMock, MagicMock, patch
import pytest
from .common import BucketDataFixture
from .common import CloudrunClientFixture


@pytest.fixture()
def bucket_data():
    with patch("policyengine_api_tagger.api.revision_tagger._get_blob") as get_blob:
        mb = BucketDataFixture(get_blob)
        yield mb


@pytest.fixture()
def cloudrun():
    with patch(
        "policyengine_api_tagger.api.revision_tagger.CloudrunClient",
        return_value=AsyncMock(),
    ) as MockCloudrunClient:
        client = AsyncMock()
        MockCloudrunClient.return_value = client
        yield CloudrunClientFixture(client)


@pytest.fixture()
def mock_storage_client():
    """Mock Google Cloud Storage client for cleanup tests."""
    with patch(
        "policyengine_api_tagger.api.revision_cleanup.storage.Client"
    ) as MockClient:
        mock_client = MagicMock()
        MockClient.return_value = mock_client
        mock_bucket = MagicMock()
        mock_client.bucket.return_value = mock_bucket
        yield {"client": mock_client, "bucket": mock_bucket}


@pytest.fixture()
def mock_cloudrun_services():
    """Mock Cloud Run ServicesAsyncClient for cleanup tests."""
    with patch(
        "policyengine_api_tagger.api.revision_cleanup.ServicesAsyncClient"
    ) as MockClient:
        mock_client = AsyncMock()
        MockClient.return_value = mock_client
        yield mock_client
