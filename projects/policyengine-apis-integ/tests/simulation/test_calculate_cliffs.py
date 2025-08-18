from policyengine_api_simulation_client import Client
from policyengine_api_simulation_client.api.default import (
    simulate_simulate_economy_comparison_post,
)
from policyengine_api_simulation_client.models import (
    SimulationOptions,
    ParametricReform,
    SimulationOptionsCountry,
    SimulationOptionsScope,
)
from policyengine_api_simulation_client.errors import UnexpectedStatus
import backoff
import httpx


@backoff.on_exception(
    backoff.expo,
    (httpx.HTTPStatusError, UnexpectedStatus),
    max_tries=5,
    giveup=lambda e: getattr(e, "response", {}).get("status_code", 0) != 503,
)
def test_calculation_cliffs(
    client: Client,
):
    options = SimulationOptions(
        country=SimulationOptionsCountry.US,  # don't use uk. It will try to load extra stuff from huggingface
        scope=SimulationOptionsScope.MACRO,
        reform=ParametricReform.from_dict(
            {"gov.irs.credits.eitc.max[0].amount": {"2026-01-01.2100-12-31": 0}}
        ),
        include_cliffs=True,
        subsample=200,  # reduce the number of households to speed things up.
        data="gs://policyengine-us-data/cps_2023.h5",  # force the service to use google storage
    )
    response = simulate_simulate_economy_comparison_post.sync(
        client=client, body=options
    )
    # Check that cliff impact data is present in the simulation result
    assert (
        response.cliff_impact is not None
    ), "Expected 'cliff_impact' to be present in the output."

    # Assert that cliff impact is non-zero in both baseline and reform scenarios
    assert response.cliff_impact.baseline.cliff_gap > 0
    assert response.cliff_impact.baseline.cliff_share > 0
    assert response.cliff_impact.reform.cliff_gap > 0
    assert response.cliff_impact.reform.cliff_share > 0
