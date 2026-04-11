from src.modal.artifact_store import GcsArtifactStore, build_artifact_store


class FakeBlob:
    def __init__(self, name: str):
        self.name = name
        self.uploads: list[tuple[bytes, str]] = []

    def upload_from_string(self, payload: bytes, content_type: str) -> None:
        self.uploads.append((payload, content_type))


class FakeBucket:
    def __init__(self):
        self.blobs: dict[str, FakeBlob] = {}

    def blob(self, name: str) -> FakeBlob:
        blob = self.blobs.get(name)
        if blob is None:
            blob = FakeBlob(name)
            self.blobs[name] = blob
        return blob


class FakeClient:
    def __init__(self):
        self.buckets: dict[str, FakeBucket] = {}

    def bucket(self, name: str) -> FakeBucket:
        bucket = self.buckets.get(name)
        if bucket is None:
            bucket = FakeBucket()
            self.buckets[name] = bucket
        return bucket


def test_build_artifact_store__returns_none_without_bucket():
    assert build_artifact_store(None) is None


def test_gcs_artifact_store__builds_structured_names_and_uploads_json():
    client = FakeClient()
    store = GcsArtifactStore(
        "test-bucket",
        prefix="diagnostics",
        client=client,
    )

    object_name = store.build_object_name(
        run_id="run-123",
        scenario="baseline",
        artifact_name="flat_trace",
        extension="json",
        country="us",
        country_package_version="1.632.5",
    )
    artifact = store.put_json(object_name, {"value": 1})

    assert object_name == (
        "diagnostics/country=us/version=1.632.5/"
        "run_id=run-123/scenario=baseline/flat_trace.json"
    )
    assert artifact.storage_uri == f"gs://test-bucket/{object_name}"
    uploaded_payload, content_type = client.bucket("test-bucket").blobs[
        object_name
    ].uploads[0]
    assert uploaded_payload == b'{"value":1}'
    assert content_type == "application/json"
