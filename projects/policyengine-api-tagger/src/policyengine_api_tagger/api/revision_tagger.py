from google.cloud import storage
from pydantic import BaseModel
from anyio import to_thread
import logging
from urllib.parse import urlparse

from .cloudrun_client import CloudrunClient

log = logging.getLogger(__file__)


class Metadata(BaseModel):
    revision: str
    models: dict[str, str]


def _get_blob(bucket: str, path: str) -> str | None:
    storage_client = storage.Client()
    blob = storage_client.bucket(bucket).blob(path)

    # Step 2: Check if file exists
    if not blob.exists():
        return None

    # Step 3: Parse the revision field from the file
    return blob.download_as_text()


def _get_blob_as_metadata_sync(bucket: str, path: str) -> Metadata | None:
    log.info(f"Looking up metadata in {bucket} at {path}")
    file_content = _get_blob(bucket, path)

    # Step 2: Check if file exists
    if not file_content:
        log.info(f"{path} does not exist in {bucket}")
        return None

    return Metadata.model_validate_json(file_content)


def _prefix_hostname(uri: str, prefix: str):
    parsed = urlparse(uri)
    # Get everything after the protocol
    rest_of_url = uri[len(parsed.scheme) + 3 :]  # +3 for "://"

    # Add prefix to hostname at the beginning
    return f"{parsed.scheme}://{prefix}{rest_of_url}"


async def _get_blob_as_metadata(bucket: str, path: str) -> Metadata | None:
    return await to_thread.run_sync(_get_blob_as_metadata_sync, bucket, path)


class RevisionTagger:
    def __init__(self, bucket_name: str):
        """
        Initialize RevisionTagger with cloud storage bucket and Cloud Run service.

        Args:
            bucket_name (str): Name of the Google Cloud Storage bucket
            cloudrun_service_name (str): Name of the Cloud Run service
        """
        self.bucket_name = bucket_name
        self.cloudrun_client = CloudrunClient()

    async def _lookup_revision(self, country: str, model_version: str) -> str | None:
        metadata = await _get_blob_as_metadata(
            self.bucket_name, f"{country}.{model_version}.json"
        )
        if metadata is None:
            return None
        return metadata.revision

    async def tag(self, country: str, model_version: str) -> str | None:
        revision_path = await self._lookup_revision(country, model_version)
        if revision_path is None:
            return None

        revision_name = revision_path.split("/")[-1]
        cloudrun_service_name = revision_path.rsplit("/revisions/", 1)[0]
        tag_string = f"country-{country}-model-{model_version.replace('.', '-')}"

        log.info(
            f"Getting tagged url for service {cloudrun_service_name}, revision {revision_name}, tag {tag_string}"
        )
        service_uri = await self.cloudrun_client.tag_revision(
            cloudrun_service_name, revision_name, tag_string
        )
        return _prefix_hostname(service_uri, f"{tag_string}---")
