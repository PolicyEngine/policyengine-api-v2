
def test_pe_uk():
    from policyengine_uk import Microsimulation

    sim = Microsimulation(dataset="hf://policyengine/policyengine-uk-data/enhanced_frs_2022_23.h5")
    print(sim.tax_benefit_system.parameters.gov.dwp.income_support.amounts)
    print(sim.calculate("pension_credit", 2025).sum()/1e9)
    sim.to_input_dataframe().to_csv("df.csv")

test_pe_uk()