"""Dataset URI normalization for simulation runtime execution."""

from __future__ import annotations

from policyengine_api_simulation.hf_dataset import (
    parse_hf_dataset_uri,
    validate_hf_dataset_uri,
    with_hf_revision,
)


def split_dataset_revision(dataset_uri: str) -> tuple[str, str | None]:
    if "@" not in dataset_uri:
        return dataset_uri, None
    dataset_without_revision, revision = dataset_uri.rsplit("@", maxsplit=1)
    if not dataset_without_revision or not revision:
        raise ValueError(f"Invalid dataset revision reference: {dataset_uri}")
    return dataset_without_revision, revision


def select_dataset_revision(
    *,
    requested_revision: str | None,
    requested_data_version: str | None,
) -> str | None:
    if (
        requested_revision is not None
        and requested_data_version is not None
        and requested_revision != requested_data_version
    ):
        raise ValueError(
            "Conflicting dataset revisions: "
            f"data requests {requested_revision!r} but data_version is "
            f"{requested_data_version!r}"
        )
    return requested_revision or requested_data_version


def _policyengine_gcs_bucket_for_hf_repo(repo_id: str) -> str | None:
    owner, separator, repo = repo_id.partition("/")
    if owner != "policyengine" or separator != "/":
        return None
    if not repo.startswith("policyengine-") or "-data" not in repo:
        return None
    return repo


def _with_gs_revision(dataset_uri: str, revision: str | None) -> str:
    without_revision, existing_revision = split_dataset_revision(dataset_uri)
    selected_revision = select_dataset_revision(
        requested_revision=existing_revision,
        requested_data_version=revision,
    )
    if selected_revision is None:
        return dataset_uri
    return f"{without_revision}@{selected_revision}"


def runtime_dataset_uri(
    dataset_uri: str,
    *,
    default_revision: str | None = None,
) -> str:
    """Convert PolicyEngine HF data artifacts to their GCS runtime URI."""

    if dataset_uri.startswith("gs://"):
        return _with_gs_revision(dataset_uri, default_revision)

    if not dataset_uri.startswith("hf://"):
        return dataset_uri

    parsed = parse_hf_dataset_uri(dataset_uri)
    if parsed is None:
        return dataset_uri

    bucket = _policyengine_gcs_bucket_for_hf_repo(parsed.repo_id)
    selected_revision = default_revision or parsed.revision
    if bucket is None:
        if default_revision is not None:
            return with_hf_revision(dataset_uri, default_revision)
        return validate_hf_dataset_uri(dataset_uri)

    if selected_revision is not None:
        return f"gs://{bucket}/{parsed.path}@{selected_revision}"

    return f"gs://{bucket}/{parsed.path}"
