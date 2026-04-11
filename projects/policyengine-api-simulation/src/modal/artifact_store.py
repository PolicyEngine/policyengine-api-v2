from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
import json
from typing import Any, Protocol

from google.cloud import storage


def _json_default(value: Any) -> str:
    if isinstance(value, datetime):
        return value.astimezone(UTC).isoformat()
    return str(value)


@dataclass(frozen=True)
class StoredArtifact:
    storage_uri: str
    object_name: str
    content_type: str
    size_bytes: int


class ArtifactStore(Protocol):
    bucket_name: str
    prefix: str

    def put_json(self, object_name: str, payload: Any) -> StoredArtifact: ...

    def put_text(self, object_name: str, payload: str) -> StoredArtifact: ...


class GcsArtifactStore:
    def __init__(
        self,
        bucket_name: str,
        *,
        prefix: str = "simulation-observability",
        client: storage.Client | None = None,
    ):
        self.bucket_name = bucket_name
        self.prefix = prefix.strip("/")
        self.client = client or storage.Client()

    def build_object_name(
        self,
        *,
        run_id: str,
        scenario: str,
        artifact_name: str,
        extension: str,
        country: str | None = None,
        country_package_version: str | None = None,
    ) -> str:
        path_parts = [self.prefix] if self.prefix else []
        if country:
            path_parts.append(f"country={country}")
        if country_package_version:
            path_parts.append(f"version={country_package_version}")
        path_parts.extend(
            [
                f"run_id={run_id}",
                f"scenario={scenario}",
                f"{artifact_name}.{extension}",
            ]
        )
        return "/".join(path_parts)

    def put_json(self, object_name: str, payload: Any) -> StoredArtifact:
        serialized = json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
            default=_json_default,
        )
        return self._put_bytes(
            object_name,
            serialized.encode("utf-8"),
            content_type="application/json",
        )

    def put_text(self, object_name: str, payload: str) -> StoredArtifact:
        return self._put_bytes(
            object_name,
            payload.encode("utf-8"),
            content_type="text/plain; charset=utf-8",
        )

    def _put_bytes(
        self,
        object_name: str,
        payload: bytes,
        *,
        content_type: str,
    ) -> StoredArtifact:
        blob = self.client.bucket(self.bucket_name).blob(object_name)
        blob.upload_from_string(payload, content_type=content_type)
        return StoredArtifact(
            storage_uri=f"gs://{self.bucket_name}/{object_name}",
            object_name=object_name,
            content_type=content_type,
            size_bytes=len(payload),
        )


def build_artifact_store(
    bucket_name: str | None,
    *,
    prefix: str = "simulation-observability",
    client: storage.Client | None = None,
) -> GcsArtifactStore | None:
    if not bucket_name:
        return None
    return GcsArtifactStore(bucket_name, prefix=prefix, client=client)
