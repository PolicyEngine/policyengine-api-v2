"""One-household native dataset shared by installed SPM integration tests."""


def materialize_native_household(source_path, tmp_path):
    import pandas as pd
    from policyengine.tax_benefit_models.us import ensure_datasets

    tiny = tmp_path / "native.h5"
    with pd.HDFStore(source_path, "r") as source, pd.HDFStore(tiny, "w") as dest:
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
