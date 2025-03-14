example_people_uk = {
    "you": {"age": {"2024": 40}, "employment_income": {"2024": 29000}},
    "your first dependent": {
        "age": {"2024": 5},
        "employment_income": {"2024": 0},
        "is_child": {"2024": True},
    },
}

# Note the difference below - inputs accept None to indicate the
# user wants to calculate this variable, while outputs should never
# contain None.
example_benunits_input_uk = {
    "your benunit": {
        "members": ["you", "your first dependent"],
        "universal_credit": {"2024": None},
    }
}

example_benunits_output_uk = {
    "your benunit": {
        "members": ["you", "your first dependent"],
        "universal_credit": {"2024": 5000.0},
    }
}

example_households_uk = {
    "your household": {
        "members": ["you", "your first dependent"],
        "country": {"2024": "ENGLAND"},
    }
}

example_household_input_uk = {
    "people": example_people_uk,
    "benunits": example_benunits_input_uk,
    "households": example_households_uk,
}

# Temporarily disabling axes to better understand schema
example_household_output_uk = {
    # "axes": None,
    "people": example_people_uk,
    "benunits": example_benunits_output_uk,
    "households": example_households_uk,
}
