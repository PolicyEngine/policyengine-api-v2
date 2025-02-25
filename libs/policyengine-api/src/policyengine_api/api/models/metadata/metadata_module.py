from pydantic import BaseModel
from .variable_module import VariableModule


class MetadataModule(BaseModel):
    variables: VariableModule
    # parameters: dict
    # entities: dict
    # variableModules: dict
    # economy_options: dict
    # current_law_id: int
    # basicInputs: dict
    # modelled_policies: dict
    # version: str
