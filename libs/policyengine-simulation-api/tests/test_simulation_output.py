

def test_simulation_output():
    from policyengine import Simulation

    sim = Simulation(**{
    "baseline": {},
    "country": "uk",
    "reform": {
        "gov.hmrc.income_tax.rates.uk[0].rate": {
        "2025-01-01.2100-12-31": 0.31
        }
    },
    "scope": "macro",
    "time_period": "2025"
    })

    result = sim.calculate_economy_comparison()

    assert result.detailed_budget["pension_credit"].baseline == -6486021485.618753