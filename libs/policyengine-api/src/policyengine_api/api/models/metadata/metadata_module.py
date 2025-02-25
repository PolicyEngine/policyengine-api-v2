from pydantic import BaseModel
from policyengine_api.api.models.metadata.variable import Variable
from policyengine_api.api.models.metadata.parameter import (
    Parameter,
    ParameterNode,
    ParameterScaleItem,
)


class MetadataModule(BaseModel):
    variables: dict[str, Variable]
    parameters: dict[str, Parameter | ParameterNode | ParameterScaleItem]
    # entities: dict
    # variableModules: dict
    # economy_options: dict
    # current_law_id: int
    # basicInputs: dict
    # modelled_policies: dict
    # version: str
