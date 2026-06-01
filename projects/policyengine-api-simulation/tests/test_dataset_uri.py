"""Tests for dataset URI normalization."""

import pytest

from policyengine_api_simulation.dataset_uri import runtime_dataset_uri


def test_runtime_dataset_uri_converts_policyengine_hf_to_gcs_without_hf_validation(
    monkeypatch,
):
    def reject_hf_validation(dataset_uri: str, revision: str) -> str:
        raise AssertionError(
            f"HF validation should not run for PolicyEngine GCS data: {dataset_uri}@{revision}"
        )

    monkeypatch.setattr(
        "policyengine_api_simulation.dataset_uri.with_hf_revision",
        reject_hf_validation,
    )

    assert (
        runtime_dataset_uri(
            "hf://policyengine/policyengine-uk-data-private/"
            "enhanced_frs_2023_24.h5@655dd07e4bb9c777b00dac044949611f1feb824f",
            default_revision="1.55.10",
        )
        == "gs://policyengine-uk-data-private/enhanced_frs_2023_24.h5@1.55.10"
    )


def test_runtime_dataset_uri_still_validates_unmanaged_hf_revisions(monkeypatch):
    def pin_hf_revision(dataset_uri: str, revision: str) -> str:
        return f"{dataset_uri.rsplit('@', maxsplit=1)[0]}@{revision}"

    monkeypatch.setattr(
        "policyengine_api_simulation.dataset_uri.with_hf_revision",
        pin_hf_revision,
    )

    assert (
        runtime_dataset_uri(
            "hf://external/example-data/file.h5@old",
            default_revision="new",
        )
        == "hf://external/example-data/file.h5@new"
    )


def test_runtime_dataset_uri_rejects_conflicting_gcs_revisions():
    with pytest.raises(ValueError, match="Conflicting dataset revisions"):
        runtime_dataset_uri(
            "gs://policyengine-uk-data-private/enhanced_frs_2023_24.h5@commit",
            default_revision="1.55.10",
        )
