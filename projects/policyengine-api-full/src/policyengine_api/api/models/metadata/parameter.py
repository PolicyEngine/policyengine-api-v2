from pydantic import BaseModel
from typing import Literal, Optional, Any


# Used for both ParameterScale and ParameterScaleBracket
class ParameterScaleItem(BaseModel):
    type: Literal["parameterNode", "parameter"]
    parameter: str
    description: Optional[str]
    label: str


class ParameterNode(ParameterScaleItem):
    economy: bool
    household: bool


class Parameter(ParameterNode):
    unit: Optional[str]
    period: Optional[str]
    values: dict[str, Any]
