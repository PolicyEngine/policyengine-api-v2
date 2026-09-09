"""One-household real formula smoke, enabled explicitly with a local native H5.

This test never loads or simulates the full population. It selects one household
and its native member records using the producer's HDF table indexes.
"""

import json
import os

import pytest

SOURCE = os.environ.get("SPM_NATIVE_SMOKE_SOURCE")
pytestmark = pytest.mark.skipif(
    not SOURCE,
    reason="Set SPM_NATIVE_SMOKE_SOURCE to the local native H5 for the bounded source integration smoke",
)


@pytest.fixture
def native_dataset(tmp_path):
    import pandas as pd
    from policyengine.tax_benefit_models.us import ensure_datasets

    tiny = tmp_path / "native.h5"
    with pd.HDFStore(SOURCE, "r") as source, pd.HDFStore(tiny, "w") as dest:
        household = source.select("household", start=0, stop=1)
        household_id = int(household.household_id.iloc[0])
        people = source.select("person", where=f"person_household_id == {household_id}")
        assert 0 < len(people) <= 20
        dest.put("household", household, format="table", data_columns=True)
        dest.put("person", people, format="table", data_columns=True)
        for entity in ("spm_unit", "tax_unit", "family", "marital_unit"):
            ids = [int(value) for value in people[f"person_{entity}_id"].unique()]
            dest.put(
                entity,
                source.select(entity, where=f"{entity}_id in {ids}"),
                format="table",
                data_columns=True,
            )
        dest.put("_time_period", source.select("_time_period"), format="table")
    # Unmanaged is an explicit test-only path; production keeps certified bundle
    # loading. This exercises the real native-to-year materializer.
    datasets = ensure_datasets(
        datasets=[str(tiny)],
        years=[2024],
        data_folder=str(tmp_path / "year-data"),
        allow_unmanaged=True,
    )
    dataset = next(iter(datasets.values()))
    dataset.load()
    assert len(dataset.data.person) == len(people)
    return dataset


def test_worker_baseline_reform_national_local_cache_and_receipts(
    native_dataset, tmp_path
):
    from policyengine.core.simulation import _cache
    from policyengine_simulation_executor.simulation_runtime import _build_simulation
    from policyengine_simulation_executor.spm import simulation_spm_result

    params = {
        "country": "us",
        "scope": "macro",
        "time_period": "2024",
        "data": str(tmp_path / "native.h5"),
        "spm": {"geography_kind": "national"},
    }
    baseline = _build_simulation(
        params, dataset=native_dataset, policy=None, region_code="us"
    )
    reform = _build_simulation(
        params,
        dataset=native_dataset,
        policy={"gov.irs.credits.ctc.amount.base[0].amount": 3000},
        region_code="us",
    )
    for simulation in (baseline, reform):
        simulation.extra_variables = {"spm_unit": ["spm_unit_spm_threshold"]}
        simulation.ensure()
        assert (
            simulation.output_dataset.data.spm_unit["spm_unit_spm_threshold"] > 0
        ).all()
    result = simulation_spm_result(baseline, reform, baseline.spm_config)
    dumped = json.loads(json.dumps(result))
    assert dumped["spm_config"] == baseline.spm_config == reform.spm_config
    assert dumped["spm_provenance"]["reform"][0]["years"]["2024"]
    original = baseline.spm_provenance()
    original["years"].clear()
    assert baseline.spm_provenance()["years"]
    # Disk replay uses the same identifier, selected config, and actual receipt.
    _cache._cache.clear()
    replay = _build_simulation(
        params, dataset=native_dataset, policy=None, region_code="us"
    )
    replay.id = baseline.id
    replay.ensure()
    assert replay.spm_provenance() == baseline.spm_provenance()
    # A shared caller id cannot reuse national output for county selection.
    local = _build_simulation(
        {**params, "spm": {"geography_kind": "county"}},
        dataset=native_dataset,
        policy=None,
        region_code="us",
    )
    local.id = baseline.id
    assert local.storage_id != baseline.storage_id
    local.ensure()
    assert local.spm_provenance()["geography_kind"] == "county"


def test_native_state_only_worker_requires_geography_and_explicit_national_works(
    native_dataset,
):
    from policyengine_simulation_executor.simulation_runtime import _build_simulation
    from policyengine_simulation_contract.spm import spm_error_detail

    native_dataset.data.household.drop(columns=["county_fips"], inplace=True)
    params = {
        "country": "us",
        "scope": "macro",
        "time_period": "2024",
        "data": "test-only-custom-data",
    }
    simulation = _build_simulation(
        params, dataset=native_dataset, policy=None, region_code="us"
    )
    with pytest.raises(ValueError) as error:
        simulation.run()
    assert spm_error_detail(error.value).code == "SPM_GEOGRAPHY_REQUIRED"
    national = _build_simulation(
        {**params, "spm": {"geography_kind": "national"}},
        dataset=native_dataset,
        policy=None,
        region_code="us",
    )
    national.run()
    assert national.spm_provenance()["geography_kind"] == "national"


def test_actual_provider_unknown_metro_is_a_typed_input_error():
    from policyengine_simulation_executor.spm import normalize_runtime_spm
    from policyengine_simulation_contract.spm import SPMInputError

    with pytest.raises(SPMInputError) as error:
        normalize_runtime_spm(
            {
                "country": "us",
                "time_period": "2024",
                "spm": {"geography_kind": "metro", "geography_id": "00000"},
            }
        )
    assert error.value.code == "SPM_GEOGRAPHY_UNAVAILABLE"
