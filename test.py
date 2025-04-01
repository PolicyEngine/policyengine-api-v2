
def test_pe_uk():
    from policyengine_uk import Microsimulation

    sim = Microsimulation(dataset="hf://policyengine/policyengine-uk-data/enhanced_frs_2022_23.h5")
    print(sim.calculate("pension_credit", 2025).sum()/1e9)

test_pe_uk()