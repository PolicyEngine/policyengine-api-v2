from pydantic import BaseModel, RootModel, Field
from typing import Union, Any, Optional


example_household_us = {
    "people": {
        "you": {"age": {"2024": 40}, "employment_income": {"2024": 29000}},
        "your first dependent": {
            "age": {"2024": 5},
            "employment_income": {"2024": 0},
            "is_tax_unit_dependent": {"2024": True},
        },
    },
    "families": {"your family": {"members": ["you", "your first dependent"]}},
    "spm_units": {
        "your household": {"members": ["you", "your first dependent"]}
    },
    "tax_units": {
        "your tax unit": {"members": ["you", "your first dependent"]}
    },
    "households": {
        "your household": {
            "members": ["you", "your first dependent"],
            "state_name": {"2024": "CA"},
        }
    },
    "marital_units": {
        "your marital unit": {"members": ["you"]},
        "your first dependent's marital unit": {
            "members": ["your first dependent"],
            "marital_unit_id": {"2024": 1},
        },
    },
}


class HouseholdAxes(BaseModel):
    name: str  # Variable over which to apply axes
    period: int | str  # The month or year to which the axes apply
    count: int  # The number of axes
    min: int  # The lowest axis
    max: int  # The highest axis


class HouseholdVariable(RootModel):
    root: Union[dict[str, Any], list[str]]


class HouseholdEntity(RootModel):
    root: dict[str, HouseholdVariable]


class HouseholdGeneric(BaseModel):
    households: dict[str, HouseholdEntity]
    people: dict[str, HouseholdEntity]
    axes: Optional[dict[str, HouseholdAxes]] = None


class HouseholdUS(HouseholdGeneric):
    families: dict[str, HouseholdEntity]
    spm_units: dict[str, HouseholdEntity]
    tax_units: dict[str, HouseholdEntity]
    marital_units: dict[str, HouseholdEntity]


class HouseholdUK(HouseholdGeneric):
    benunits: dict[str, HouseholdEntity]


# Typing alias for all three possible household models
HouseholdData = Union[HouseholdUS, HouseholdUK, HouseholdGeneric]
