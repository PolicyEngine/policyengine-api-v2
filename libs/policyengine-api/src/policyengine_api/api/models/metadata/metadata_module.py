from pydantic import BaseModel
from typing import Optional
from policyengine_api.api.models.metadata.entity import Entity
from policyengine_api.api.models.metadata.economy_options import EconomyOptions
from policyengine_api.api.models.metadata.modelled_policies import (
    ModelledPolicies,
)
from policyengine_api.api.models.metadata.parameter import (
    Parameter,
    ParameterNode,
    ParameterScaleItem,
)
from policyengine_api.api.models.metadata.variable import (
    Variable,
    VariableModule,
)


class MetadataModule(BaseModel):
    variables: dict[str, Variable]
    parameters: dict[str, Parameter | ParameterNode | ParameterScaleItem]
    entities: dict[str, Entity]
    variableModules: dict[str, VariableModule]
    economy_options: EconomyOptions
    basicInputs: list[str]
    modelled_policies: Optional[ModelledPolicies]
    current_law_id: int
    version: str
