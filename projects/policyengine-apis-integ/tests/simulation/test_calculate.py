import policyengine_simulation_api_client
from policyengine_simulation_api_client.exceptions import ServiceException
import backoff


@backoff.on_exception(
    backoff.expo,
    ServiceException,
    max_tries=5,
    giveup=lambda e: getattr(e, "status", None) != 503,
)
def test_calculation(client: policyengine_simulation_api_client.DefaultApi):
    options = policyengine_simulation_api_client.SimulationOptions(
        country="us",  # don't use uk. It will try to load extra stuff from huggingface
        scope="macro",
        reform={
            "gov.irs.credits.ctc.refundable.fully_refundable": policyengine_simulation_api_client.ParametricReformValue.from_dict(
                {"2023-01-01.2100-12-31": True}
            )
        },
        subsample=200,  # reduce the number of households to speed things up.
        data=policyengine_simulation_api_client.Data(
            "gs://policyengine-us-data/cps_2023.h5"
        ),  # force the service to use google storage (policyengine.py defaults to huggingface)
    )
    response = client.simulate_simulate_economy_comparison_post(options)
