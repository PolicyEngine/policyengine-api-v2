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
def test_calculation(client: Client):
    options = SimulationOptions(
        country=SimulationOptionsCountry.US,  # don't use uk. It will try to load extra stuff from huggingface
        scope=SimulationOptionsScope.MACRO,
        reform=ParametricReform.from_dict(
            {
                "gov.irs.credits.ctc.refundable.fully_refundable": {
                    "2023-01-01.2100-12-31": True
                }
            }
        ),
        subsample=200,  # reduce the number of households to speed things up.
        data="gs://policyengine-us-data/enhanced_cps_2024.h5",  # force the service to use google storage (policyengine.py defaults to huggingface)
    )
    response = simulate_simulate_economy_comparison_post.sync(
        client=client, body=options
    )
