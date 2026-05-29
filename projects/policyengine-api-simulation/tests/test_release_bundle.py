"""Tests for policyengine.py release bundle helpers."""

import pytest

from policyengine_api_simulation.release_bundle import (
    get_country_release_bundle,
    resolve_bundle_dataset_name,
    resolve_bundle_dataset_uri,
)


@pytest.fixture(autouse=True)
def stub_hf_revision_validation(monkeypatch):
    monkeypatch.setattr(
        "policyengine_api_simulation.release_bundle.with_hf_revision",
        lambda dataset_uri, revision: (
            f"{dataset_uri.rsplit('@', maxsplit=1)[0]}@{revision}"
            if dataset_uri.startswith("hf://")
            else dataset_uri
        ),
    )


def test_country_release_bundle_exposes_model_and_data_versions():
    us_bundle = get_country_release_bundle("us")
    uk_bundle = get_country_release_bundle("uk")

    assert us_bundle.model_package_name == "policyengine-us"
    assert us_bundle.model_version
    assert us_bundle.data_package_name == "policyengine-us-data"
    assert us_bundle.data_version
    assert uk_bundle.model_package_name == "policyengine-uk"
    assert uk_bundle.model_version
    assert uk_bundle.data_package_name == "policyengine-uk-data"
    assert uk_bundle.data_version


def test_resolve_bundle_dataset_name_uses_manifest_default():
    assert (
        resolve_bundle_dataset_name("us", None)
        == get_country_release_bundle("us").default_dataset
    )
    assert (
        resolve_bundle_dataset_name("uk", None)
        == get_country_release_bundle("uk").default_dataset
    )


def test_resolve_bundle_dataset_uri_maps_known_aliases_to_manifest_uris():
    assert (
        resolve_bundle_dataset_uri("us", "enhanced_cps")
        == get_country_release_bundle("us").default_dataset_uri
    )
    assert (
        resolve_bundle_dataset_uri("uk", "enhanced_frs")
        == get_country_release_bundle("uk").default_dataset_uri
    )


def test_resolve_bundle_dataset_uri_preserves_explicit_dataset_uri_and_revision():
    uri = "hf://policyengine/policyengine-us-data/enhanced_cps_2024.h5@1.110.12"

    assert resolve_bundle_dataset_name("us", uri) == uri
    assert resolve_bundle_dataset_uri("us", uri) == uri


def test_resolve_bundle_dataset_uri_maps_explicit_logical_revision_to_hf_uri():
    dataset = "enhanced_cps_2024@1.110.12"

    assert resolve_bundle_dataset_name("us", dataset).startswith(
        "hf://policyengine/policyengine-us-data/enhanced_cps_2024.h5@1.110.12"
    )
    assert resolve_bundle_dataset_uri("us", dataset).startswith(
        "hf://policyengine/policyengine-us-data/enhanced_cps_2024.h5@1.110.12"
    )


def test_resolve_bundle_dataset_uri_preserves_explicit_gcs_uri():
    uri = "gs://policyengine-us-data/enhanced_cps_2024.h5"

    assert resolve_bundle_dataset_name("us", uri) == uri
    assert resolve_bundle_dataset_uri("us", uri) == uri


def test_resolve_bundle_dataset_uri_supports_legacy_us_aliases():
    assert resolve_bundle_dataset_uri("us", "cps") == (
        "hf://policyengine/policyengine-us-data/cps_2023.h5@1.110.12"
    )
    assert resolve_bundle_dataset_uri("us", "pooled_cps") == (
        "hf://policyengine/policyengine-us-data/pooled_3_year_cps_2023.h5@1.110.12"
    )


def test_resolve_bundle_dataset_uri_preserves_unmanaged_unknown_values():
    assert resolve_bundle_dataset_uri("us", "custom_dataset_label") == (
        "custom_dataset_label"
    )


def test_resolve_bundle_dataset_uri_rejects_unknown_logical_revision():
    with pytest.raises(ValueError, match="Unknown dataset revision reference"):
        resolve_bundle_dataset_uri("us", "custom_dataset_label@1.0.0")
