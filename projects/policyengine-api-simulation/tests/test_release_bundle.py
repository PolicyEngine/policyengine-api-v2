"""Tests for policyengine.py release bundle helpers."""

from src.modal.release_bundle import (
    get_country_release_bundle,
    resolve_bundle_dataset_name,
    resolve_bundle_dataset_uri,
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


def test_resolve_bundle_dataset_uri_preserves_unmanaged_unknown_values():
    assert resolve_bundle_dataset_uri("us", "custom_dataset_label") == (
        "custom_dataset_label"
    )
