"""Certified SPM runtime selection, independent of caller-supplied metadata."""

from functools import lru_cache

from policyengine_simulation_contract.spm import (
    SPMCapability,
    SPMInputError,
    SPMProvenance,
    combine_spm_results,
    resolve_spm_selection,
    spm_error_detail,
)


@lru_cache(maxsize=4)
def _forecast(expected_sha256):
    from spm_calculator import load_forecast

    return load_forecast(expected_sha256=expected_sha256)


def runtime_spm_capability():
    from policyengine.bundle import get_current_bundle
    from policyengine.core import Simulation

    try:
        bundle = get_current_bundle()
        configured = bundle.get("measurements", {}).get("spm")
    except (ImportError, ValueError, TypeError, AttributeError) as exc:
        raise SPMInputError(
            "SPM_CONFIGURATION_UNAVAILABLE",
            "The installed SPM bundle configuration is unavailable",
        ) from exc
    if configured is None:
        return None
    if "spm" not in Simulation.model_fields or not hasattr(
        Simulation, "spm_provenance"
    ):
        raise SPMInputError(
            "SPM_CONFIGURATION_UNAVAILABLE",
            "The installed wrapper does not support canonical SPM",
        )
    try:
        from policyengine_us import Microsimulation

        if not (
            hasattr(Microsimulation, "spm_config")
            and callable(getattr(Microsimulation, "spm_provenance", None))
        ):
            raise ValueError("The installed US model does not support canonical SPM")
        capability = SPMCapability(defaults=configured)
        forecast = _forecast(capability.defaults.forecast_content_sha256)
        forecast.entry(
            forecast.years[0],
            scenario=capability.defaults.scenario,
            as_of=capability.defaults.as_of,
        )
        return capability
    except (ImportError, ValueError, TypeError, OSError) as exc:
        raise SPMInputError("SPM_CONFIGURATION_UNAVAILABLE", str(exc)) from exc


def normalize_runtime_spm(params):
    """Resolve before dataset loading, artifact lookup, or child submission."""
    from policyengine_simulation_executor.release_bundle import (
        get_country_release_bundle,
    )

    country = params.get("country", "us").lower()
    bundle = get_country_release_bundle(country)
    selection = resolve_spm_selection(
        country,
        params.get("spm"),
        capability=runtime_spm_capability() if country == "us" else None,
        policyengine_version=bundle.policyengine_version,
        model_version=bundle.model_version,
    )
    if selection is not None:
        try:
            from spm_calculator.policyengine_adapter import PolicyEngineSPMProvider

            forecast = _forecast(selection["forecast_content_sha256"])
            if selection["county_vintage"] != "2020":
                raise ValueError("Unsupported county vintage: use 2020")
            provider = PolicyEngineSPMProvider(
                forecast,
                **{
                    key: value
                    for key, value in selection.items()
                    if key != "forecast_content_sha256"
                },
            )
            from policyengine_simulation_executor.simulation_runtime import _parse_year

            start = int(params.get("start_year") or _parse_year(params))
            for year in range(start, start + int(params.get("window_size", 1))):
                # Use the country adapter's typed year contract. This temporary
                # provider validates metadata without measuring any SPM amount
                # or modifying the actual simulation's calculation receipts.
                provider.year_metadata(year)
                if selection["geography_kind"] == "metro":
                    try:
                        forecast.geography_factor(
                            year,
                            "renter",
                            kind="metro",
                            geoid=selection["geography_id"],
                            scenario=selection["scenario"],
                            as_of=selection["as_of"],
                        )
                    except ValueError as exc:
                        raise SPMInputError(
                            "SPM_GEOGRAPHY_UNAVAILABLE", str(exc)
                        ) from None
        except ValueError as exc:
            detail = spm_error_detail(exc)
            if detail:
                raise SPMInputError(detail.code, detail.message) from exc
            # The installed provider constructor still exposes the forecast's
            # plain scenario error; use the same narrow translation as the
            # calculator's Frame and Axiom adapters, leaving other errors alone.
            if str(exc).startswith("Unknown forecast scenario:"):
                raise SPMInputError("SPM_SCENARIO_UNAVAILABLE", str(exc)) from exc
            raise SPMInputError("SPM_SETTINGS_INVALID", str(exc)) from exc
    return selection


def simulation_spm_result(baseline, reform, selection, *, expected_year=None):
    if selection is None:
        return {}
    receipts = []
    for simulation in (baseline, reform):
        if simulation.spm_config != selection:
            raise SPMInputError(
                "SPM_CONFIGURATION_UNAVAILABLE",
                "Simulation ignored the requested SPM selection",
            )
        try:
            receipts.append(
                SPMProvenance.model_validate(simulation.spm_provenance()).model_dump(
                    mode="json"
                )
            )
        except ValueError as exc:
            raise SPMInputError(
                "SPM_CONFIGURATION_UNAVAILABLE",
                "Simulation has no valid SPM calculation receipt",
            ) from exc
    return combine_spm_results(
        [
            {
                "spm_config": selection,
                "spm_provenance": {"baseline": [receipts[0]], "reform": [receipts[1]]},
            }
        ],
        selection,
        expected_year=expected_year,
    )
