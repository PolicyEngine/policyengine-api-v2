example_people_us = {
    "you": {"age": {"2024": 40}, "employment_income": {"2024": 29000}},
    "your first dependent": {
        "age": {"2024": 5},
        "employment_income": {"2024": 0},
        "is_tax_unit_dependent": {"2024": True},
    },
}

example_families_us = {
    "your family": {"members": ["you", "your first dependent"]}
}

example_spm_units_us = {
    "your household": {"members": ["you", "your first dependent"]}
}

# Note the difference below - inputs accept None to indicate the
# user wants to calculate this variable, while outputs should never
# contain None.
example_tax_units_input_us = {
    "your tax unit": {
        "members": ["you", "your first dependent"],
        "eitc": {"2024": 39_000},
        "ctc": {"2024": None},
    }
}

example_tax_units_output_us = {
    "your tax unit": {
        "members": ["you", "your first dependent"],
        "eitc": {"2024": 39_000},
        "ctc": {"2024": 1_500},
    }
}

example_households_us = {
    "your household": {
        "members": ["you", "your first dependent"],
        "state_name": {"2024": "CA"},
    }
}

example_marital_units_us = {
    "your marital unit": {"members": ["you"]},
    "your first dependent's marital unit": {
        "members": ["your first dependent"],
        "marital_unit_id": {"2024": 1},
    },
}


example_household_input_us = {
    "people": example_people_us,
    "families": example_families_us,
    "spm_units": example_spm_units_us,
    "tax_units": example_tax_units_input_us,
    "households": example_households_us,
    "marital_units": example_marital_units_us,
}

# Temporarily disabling axes to better understand schema
example_household_output_us = {
    # "axes": None,
    "people": example_people_us,
    "families": example_families_us,
    "spm_units": example_spm_units_us,
    "tax_units": example_tax_units_output_us,
    "households": example_households_us,
    "marital_units": example_marital_units_us,
}
