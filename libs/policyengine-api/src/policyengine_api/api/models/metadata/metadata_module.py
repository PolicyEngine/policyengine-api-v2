from pydantic import BaseModel
from policyengine_api.api.models.metadata.variable import (
    Variable,
    VariableModule,
)
from policyengine_api.api.models.metadata.entity import Entity
from policyengine_api.api.models.metadata.parameter import (
    Parameter,
    ParameterNode,
    ParameterScaleItem,
)
from policyengine_api.api.models.metadata.economy_options import EconomyOptions


class MetadataModule(BaseModel):
    variables: dict[str, Variable]
    parameters: dict[str, Parameter | ParameterNode | ParameterScaleItem]
    entities: dict[str, Entity]
    variableModules: dict[str, VariableModule]
    economy_options: EconomyOptions
    # basicInputs: dict
    # modelled_policies: dict
    # version: str
    current_law_id: int
