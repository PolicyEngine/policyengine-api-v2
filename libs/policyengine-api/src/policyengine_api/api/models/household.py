from pydantic import BaseModel, RootModel, Field
from typing import Union, Any, Optional
from policyengine_api.api.data.examples.example_household_us import (
    example_people_us,
    example_families_us,
    example_spm_units_us,
    example_tax_units_input_us,
    example_households_us,
    example_marital_units_us,
)

# Temporarily disabling axes to better understand schema
# class HouseholdAxes(BaseModel):
#     name: str  # Variable over which to apply axes
#     period: int | str  # The month or year to which the axes apply
#     count: int  # The number of axes
#     min: int  # The lowest axis
#     max: int  # The highest axis


class HouseholdVariable(RootModel):
    root: Union[dict[str, Any], list[str]]


class HouseholdEntity(RootModel):
    root: dict[str, HouseholdVariable]


class HouseholdGeneric(BaseModel):
    households: dict[str, HouseholdEntity] = Field(
        examples=[example_households_us]
    )
    people: dict[str, HouseholdEntity] = Field(examples=[example_people_us])
    # axes: Optional[HouseholdAxes] = None


class HouseholdUS(HouseholdGeneric):
    families: Optional[dict[str, HouseholdEntity]] = Field(
        default={}, examples=[example_families_us]
    )
    spm_units: Optional[dict[str, HouseholdEntity]] = Field(
        default={}, examples=[example_spm_units_us]
    )
    tax_units: Optional[dict[str, HouseholdEntity]] = Field(
        default={}, examples=[example_tax_units_input_us]
    )
    marital_units: Optional[dict[str, HouseholdEntity]] = Field(
        default={}, examples=[example_marital_units_us]
    )


class HouseholdUK(HouseholdGeneric):
    benunits: Optional[dict[str, HouseholdEntity]] = {}


# Typing alias for all three possible household models
HouseholdData = Union[HouseholdUS, HouseholdUK, HouseholdGeneric]
