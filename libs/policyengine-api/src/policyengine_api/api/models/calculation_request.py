from pydantic import BaseModel, Field, SerializationInfo, field_validator
from typing import Optional, Any
import datetime
from policyengine_api.api.country import COUNTRIES

current_year = datetime.datetime.now().year

class VariableModule(BaseModel):
    root: dict[str, Any]

    # Add validator to check that variable present in country package?

class VariableString(str):
    root: str

    # Add validator to check that variable present in country package?
    @field_validator("root", mode="after")
    @classmethod
    def validate_variable_string(cls, value: str, info: SerializationInfo) -> str:
        context = info.context
        if context and "country_id" in context:

            # TODO: Clean up, make into one function, then call within VariableString and VariableModule
            country_id = context["country_id"]
            country = COUNTRIES.get(country_id)
            metadata = country.metadata
            variables = metadata.variables

            if value not in variables:
                raise ValueError(f"Variable {value} does not exist in country {country_id}")
        return value

class IndividualEntity(BaseModel):
    id: Optional[str] = None # Need to figure out way to autogenerate this if not provided
    variables: VariableModule

class GroupEntity(IndividualEntity):
    members: list[str] = [] # Can we validate that members are extant ids?

class CalculationRequest(BaseModel):
    simulation_year: int = Field(default=current_year)
    persons: list[IndividualEntity]
    households: Optional[list[GroupEntity]] = []
    tax_units: Optional[list[GroupEntity]] = []
    spm_units: Optional[list[GroupEntity]] = []
    families: Optional[list[GroupEntity]] = []
    marital_units: Optional[list[GroupEntity]] = []
    variables_to_calculate: list[VariableString]


