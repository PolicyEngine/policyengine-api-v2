import policyengine_simulation_api_client
import pytest

# I don't love this client. We should investigate alternatives.
# the package structure is really tedious to use
# it doesn't define methods on the client so it's not very OO
# and it returns a union instead of just throwing an exception
def test_ping(client: policyengine_simulation_api_client.DefaultApi):
    response = client.ping_ping_post(
        policyengine_simulation_api_client.PingRequest(value=12)
    )
    assert response.incremented == 13


def test_calculation(client: policyengine_simulation_api_client.DefaultApi):
    options = policyengine_simulation_api_client.SimulationOptions(
            country="us",
            scope="macro",
            reform={
                "gov.irs.credits.ctc.refundable.fully_refundable": policyengine_simulation_api_client.ParametricReformValue.from_dict({"2023-01-01.2100-12-31":True})
            },
            subsample=200, # reduce the number of households to speed things up.
            data=policyengine_simulation_api_client.Data("gs://policyengine-us-data/cps_2023.h5") # force the service to use google storage (policyengine.py defaults to huggingface)
        )
    response = client.simulate_simulate_economy_comparison_post(
        options
    )
