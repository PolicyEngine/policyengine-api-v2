"""Tests for Hugging Face dataset revision validation helpers."""

from __future__ import annotations

import json

import pytest

import policyengine_api_simulation.hf_dataset as hf_dataset
from policyengine_api_simulation.hf_dataset import (
    HuggingFaceDatasetReferenceError,
    parse_hf_dataset_uri,
    validate_hf_dataset_uri,
    with_hf_revision,
)


class _FakeResponse:
    def __init__(self, payload: dict):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return None

    def read(self):
        return json.dumps(self.payload).encode("utf-8")


def test_parse_hf_dataset_uri_extracts_repo_path_and_revision():
    parsed = parse_hf_dataset_uri(
        "hf://policyengine/policyengine-us-data/enhanced_cps_2024.h5@1.77.0"
    )

    assert parsed is not None
    assert parsed.repo_id == "policyengine/policyengine-us-data"
    assert parsed.path == "enhanced_cps_2024.h5"
    assert parsed.revision == "1.77.0"


def test_fetch_hf_dataset_revision_uses_dataset_revision_api(monkeypatch):
    hf_dataset._fetch_hf_dataset_revision.cache_clear()
    seen = {}

    def fake_urlopen(request, timeout):
        seen["url"] = request.full_url
        seen["headers"] = dict(request.header_items())
        seen["timeout"] = timeout
        return _FakeResponse({"sha": "abc123", "siblings": []})

    monkeypatch.setattr(hf_dataset, "urlopen", fake_urlopen)

    payload = hf_dataset._fetch_hf_dataset_revision(
        "policyengine/policyengine-us-data",
        "1.77.0",
        "hf-token",
    )

    assert payload == {"sha": "abc123", "siblings": []}
    assert seen["url"] == (
        "https://huggingface.co/api/datasets/"
        "policyengine/policyengine-us-data/revision/1.77.0"
    )
    assert seen["headers"]["Authorization"] == "Bearer hf-token"
    assert seen["timeout"] == hf_dataset.HF_REQUEST_TIMEOUT_SECONDS


def test_validate_hf_dataset_uri_rejects_revision_missing_artifact(monkeypatch):
    monkeypatch.setattr(
        hf_dataset,
        "_fetch_hf_dataset_revision",
        lambda repo_id, revision, token: {"siblings": [{"rfilename": "other_file.h5"}]},
    )

    with pytest.raises(
        HuggingFaceDatasetReferenceError,
        match="does not contain artifact",
    ):
        validate_hf_dataset_uri(
            "hf://policyengine/policyengine-us-data/enhanced_cps_2024.h5@1.77.0"
        )


def test_with_hf_revision_validates_and_preserves_requested_revision(monkeypatch):
    calls = []

    def fake_validate(dataset_uri):
        calls.append(dataset_uri)
        return dataset_uri

    monkeypatch.setattr(hf_dataset, "validate_hf_dataset_uri", fake_validate)

    assert (
        with_hf_revision(
            "hf://policyengine/policyengine-us-data/enhanced_cps_2024.h5@1.110.12",
            "1.77.0",
        )
        == "hf://policyengine/policyengine-us-data/enhanced_cps_2024.h5@1.77.0"
    )
    assert calls == [
        "hf://policyengine/policyengine-us-data/enhanced_cps_2024.h5@1.77.0"
    ]
