from pydantic import BaseModel
from typing import Any, Optional
from policyengine_api.api.enums import (
    PERIODS,
    VALUE_TYPES,
    ENTITIES_US,
    ENTITIES_UK,
    ENTITIES_GENERIC,
)


class Variable(BaseModel):
    documentation: Optional[str]  # Perhaps enforce no None's?
    entity: ENTITIES_US | ENTITIES_UK | ENTITIES_GENERIC
    valueType: VALUE_TYPES
    definitionPeriod: PERIODS
    name: str
    label: str
    category: Optional[str]
    unit: Optional[str]  # Perhaps enforce no None's?
    moduleName: str
    indexInModule: Optional[int]  # Perhaps enforce no None's?
    isInputVariable: bool
    defaultValue: int | float | bool | str | None
    adds: list[str] | str | None
    subtracts: list[str] | str | None
    hidden_input: bool
    possibleValues: Optional[list[dict[str, Any]]] | None = []


class VariableModule(BaseModel):
    label: str
    description: Optional[str]
    index: Optional[
        int
    ]  # This is None in only one case in the UK that I've found; perhaps enforce no None's?
