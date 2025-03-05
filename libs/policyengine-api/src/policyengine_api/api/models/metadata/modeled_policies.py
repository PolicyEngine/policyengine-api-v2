from pydantic import BaseModel, RootModel
from typing import Optional


class ModeledPoliciesBreakdown(BaseModel):
    modelled: list[str]
    not_modelled: Optional[list[str]] = []


# E.g., "IRELAND" in UK, "AZ" in US
class FilteredPoliciesEntity(RootModel):
    root: dict[str, ModeledPoliciesBreakdown]


# E.g., "country" in UK, "state" in US
class FilteredPoliciesEntityType(RootModel):
    root: dict[str, FilteredPoliciesEntity]


class ModeledPolicies(BaseModel):
    core: ModeledPoliciesBreakdown
    filtered: FilteredPoliciesEntityType
