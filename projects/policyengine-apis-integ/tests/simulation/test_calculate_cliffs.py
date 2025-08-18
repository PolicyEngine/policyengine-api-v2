import policyengine_api_simulation_client
from policyengine_api_simulation_client.exceptions import ServiceException
import backoff


@backoff.on_exception(
    backoff.expo,
    ServiceException,
    max_tries=5,
    giveup=lambda e: getattr(e, "status", None) != 503,
)
def test_calculation_cliffs(
    client: policyengine_api_simulation_client.DefaultApi,
):
    options = policyengine_api_simulation_client.SimulationOptions(
        country="us",  # don't use uk. It will try to load extra stuff from huggingface
        scope="macro",
        reform={
            "gov.irs.credits.eitc.max[0].amount": policyengine_api_simulation_client.ParametricReformValue.from_dict(
                {"2026-01-01.2100-12-31": 0}
            )
        },
        include_cliffs=True,  # type: ignore
        subsample=200,  # reduce the number of households to speed things up.
        data=policyengine_api_simulation_client.Data(
            "gs://policyengine-us-data/cps_2023.h5"
        ),  # force the service to use google storage
    )
    response = client.simulate_simulate_economy_comparison_post(options)
    result = response.to_dict()
    # Check that cliff impact data is present in the simulation result
    cliffs = result.get("cliff_impact")
    assert cliffs is not None, "Expected 'cliff_impact' to be present in the output."

    # Assert that cliff impact is non-zero in both baseline and reform scenarios
    assert cliffs["baseline"]["cliff_gap"] > 0
    assert cliffs["baseline"]["cliff_share"] > 0
    assert cliffs["reform"]["cliff_gap"] > 0
    assert cliffs["reform"]["cliff_share"] > 0
