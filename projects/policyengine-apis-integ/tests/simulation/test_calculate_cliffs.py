import policyengine_simulation_api_client

def test_calculation_cliffs(client: policyengine_simulation_api_client.DefaultApi):
    options = policyengine_simulation_api_client.SimulationOptions(
            country="us", # don't use uk. It will try to load extra stuff from huggingface
            scope="macro",
            reform = {
                "gov.irs.credits.eitc.max[0].amount": policyengine_simulation_api_client.ParametricReformValue.from_dict({
                    "2026-01-01.2100-12-31": 0
                })
            },
            include_cliffs=True,
            subsample=200, # reduce the number of households to speed things up.
            data=policyengine_simulation_api_client.Data("gs://policyengine-us-data/cps_2023.h5") # force the service to use google storage (policyengine.py defaults to huggingface)
        )
    response = client.simulate_simulate_economy_comparison_post(
        options
    )
    result = response.to_dict()
    # Check for cliffs
    cliffs = result.get('cliff_impact')
    assert cliffs is not None, "Expected cliffs to be present in the output."
