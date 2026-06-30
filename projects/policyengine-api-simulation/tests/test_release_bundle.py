"""Tests for policyengine.py release bundle helpers."""

import pytest

from policyengine_api_simulation.release_bundle import (
    BUNDLE_RECEIPT_FILENAME,
    get_country_release_bundle,
    resolve_bundle_dataset_name,
    resolve_bundle_dataset_uri,
    resolve_runtime_bundle_dataset_uri,
)


@pytest.fixture(autouse=True)
def stub_hf_revision_validation(monkeypatch):
    def with_revision(dataset_uri, revision):
        return (
            f"{dataset_uri.rsplit('@', maxsplit=1)[0]}@{revision}"
            if dataset_uri.startswith("hf://")
            else dataset_uri
        )

    monkeypatch.setattr(
        "policyengine_api_simulation.dataset_uri.with_hf_revision",
        with_revision,
    )


def test_country_release_bundle_exposes_model_and_data_versions():
    us_bundle = get_country_release_bundle("us")
    uk_bundle = get_country_release_bundle("uk")

    assert us_bundle.model_package_name == "policyengine-us"
    assert us_bundle.model_version
    assert us_bundle.data_package_name == "populace-data"
    assert us_bundle.data_version
    assert us_bundle.data_artifact_revision
    assert us_bundle.default_dataset == "populace_us_2024"
    assert us_bundle.default_dataset_uri.startswith("hf://policyengine/populace-us/")
    assert uk_bundle.model_package_name == "policyengine-uk"
    assert uk_bundle.model_version
    assert uk_bundle.data_package_name == "populace-data"
    assert uk_bundle.data_version
    assert uk_bundle.data_artifact_revision
    assert uk_bundle.default_dataset == "populace_uk_2023"
    assert uk_bundle.default_dataset_uri.startswith(
        "hf://policyengine/populace-uk-private/"
    )


def test_resolve_bundle_dataset_name_uses_manifest_default():
    assert (
        resolve_bundle_dataset_name("us", None)
        == get_country_release_bundle("us").default_dataset
    )
    assert (
        resolve_bundle_dataset_name("uk", None)
        == get_country_release_bundle("uk").default_dataset
    )


def test_resolve_bundle_dataset_uri_maps_certified_defaults_to_manifest_uris():
    assert (
        resolve_bundle_dataset_uri(
            "us", get_country_release_bundle("us").default_dataset
        )
        == get_country_release_bundle("us").default_dataset_uri
    )
    assert (
        resolve_bundle_dataset_uri(
            "uk", get_country_release_bundle("uk").default_dataset
        )
        == get_country_release_bundle("uk").default_dataset_uri
    )


def test_resolve_bundle_dataset_uri_does_not_certify_us_state_sidecars():
    bundle = get_country_release_bundle("us")

    assert "states/UT" not in bundle.dataset_uris
    assert resolve_bundle_dataset_uri("us", "states/UT") == "states/UT"


def test_resolve_bundle_dataset_uri_keeps_legacy_aliases_as_explicit_overrides():
    assert resolve_bundle_dataset_uri("us", "enhanced_cps") == (
        "hf://policyengine/policyengine-us-data/enhanced_cps_2024.h5@1.110.12"
    )
    assert (
        resolve_bundle_dataset_uri("uk", "enhanced_frs")
        == (get_country_release_bundle("uk").dataset_uris["enhanced_frs_2023_24"])
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


def test_resolve_runtime_bundle_dataset_uri_maps_default_to_gcs_version():
    bundle = get_country_release_bundle("us")

    assert resolve_runtime_bundle_dataset_uri("us", None) == bundle.default_dataset_uri


def test_resolve_runtime_bundle_dataset_uri_maps_alias_to_gcs_version():
    bundle = get_country_release_bundle("uk")

    assert resolve_runtime_bundle_dataset_uri("uk", "enhanced_frs").startswith(
        "gs://policyengine-uk-data-private/enhanced_frs_2023_24.h5@"
    )
    assert bundle.default_dataset == "populace_uk_2023"


def test_resolve_runtime_bundle_dataset_uri_applies_requested_version():
    assert (
        resolve_runtime_bundle_dataset_uri(
            "us",
            "enhanced_cps_2024",
            "1.77.0",
        )
        == "gs://policyengine-us-data/enhanced_cps_2024.h5@1.77.0"
    )


def test_resolve_runtime_bundle_dataset_uri_preserves_explicit_hf_data_version():
    assert (
        resolve_runtime_bundle_dataset_uri(
            "us",
            "hf://policyengine/policyengine-us-data/enhanced_cps_2024.h5@1.77.0",
        )
        == "gs://policyengine-us-data/enhanced_cps_2024.h5@1.77.0"
    )


def test_resolve_runtime_bundle_dataset_uri_preserves_explicit_gcs_data_version():
    assert (
        resolve_runtime_bundle_dataset_uri(
            "us",
            "gs://policyengine-us-data/enhanced_cps_2024.h5@1.77.0",
        )
        == "gs://policyengine-us-data/enhanced_cps_2024.h5@1.77.0"
    )


def test_resolve_runtime_bundle_dataset_uri_preserves_unmanaged_unknown_values():
    assert (
        resolve_runtime_bundle_dataset_uri("us", "custom_dataset_label")
        == "custom_dataset_label"
    )


def test_resolve_runtime_bundle_dataset_uri_preserves_explicit_gcs_uri():
    uri = "gs://policyengine-us-data/enhanced_cps_2024.h5"

    assert resolve_runtime_bundle_dataset_uri("us", uri) == uri


def test_resolve_runtime_bundle_dataset_uri_prefers_installed_default_dataset(
    tmp_path, monkeypatch
):
    bundle = get_country_release_bundle("us")
    dataset_path = tmp_path / f"{bundle.default_dataset}.h5"
    dataset_path.write_bytes(b"data")
    receipt_path = tmp_path / BUNDLE_RECEIPT_FILENAME
    receipt_path.write_text(
        """
        {
          "bundle_version": "4.18.3",
          "policyengine_version": "4.18.3",
          "datasets": [
            {
              "country": "us",
              "dataset": "%s",
              "version": "%s",
              "path": "%s"
            }
          ]
        }
        """
        % (bundle.default_dataset, bundle.data_version, str(dataset_path)),
        encoding="utf-8",
    )
    monkeypatch.setenv("POLICYENGINE_BUNDLE_RECEIPT", str(receipt_path))
    get_country_release_bundle.cache_clear()

    assert resolve_runtime_bundle_dataset_uri("us", None) == str(dataset_path)
    assert resolve_runtime_bundle_dataset_uri("us", bundle.default_dataset) == str(
        dataset_path
    )


def test_resolve_runtime_bundle_dataset_uri_preserves_nondefault_override_with_receipt(
    tmp_path, monkeypatch
):
    bundle = get_country_release_bundle("us")
    dataset_path = tmp_path / f"{bundle.default_dataset}.h5"
    dataset_path.write_bytes(b"data")
    receipt_path = tmp_path / BUNDLE_RECEIPT_FILENAME
    receipt_path.write_text(
        """
        {
          "datasets": [
            {
              "country": "us",
              "dataset": "%s",
              "version": "%s",
              "path": "%s"
            }
          ]
        }
        """
        % (bundle.default_dataset, bundle.data_version, str(dataset_path)),
        encoding="utf-8",
    )
    monkeypatch.setenv("POLICYENGINE_BUNDLE_RECEIPT", str(receipt_path))
    get_country_release_bundle.cache_clear()

    assert resolve_runtime_bundle_dataset_uri("us", "cps") == (
        "gs://policyengine-us-data/cps_2023.h5@1.110.12"
    )
