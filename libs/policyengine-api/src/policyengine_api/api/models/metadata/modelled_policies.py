from pydantic import BaseModel, RootModel
from typing import Optional


class ModelledPoliciesBreakdown(BaseModel):
    modelled: list[str]
    not_modelled: Optional[list[str]] = None


# E.g., "IRELAND" in UK, "AZ" in US
class FilteredPoliciesEntity(RootModel):
    root: dict[str, ModelledPoliciesBreakdown]


# E.g., "country" in UK, "state" in US
class FilteredPoliciesEntityType(RootModel):
    root: dict[str, FilteredPoliciesEntity]


class ModelledPolicies(BaseModel):
    core: ModelledPoliciesBreakdown
    filtered: FilteredPoliciesEntityType
