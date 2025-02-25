from pydantic import BaseModel
from typing import Any, Optional
from policyengine_api.api.utils.enums import (
    PERIODS,
    VALUE_TYPES,
    ENTITIES_US,
    ENTITIES_UK,
    ENTITIES_GENERIC,
)


class Variable(BaseModel):
    documentation: str | None  # Perhaps enforce no None's?
    entity: ENTITIES_US | ENTITIES_UK | ENTITIES_GENERIC
    valueType: VALUE_TYPES
    definitionPeriod: PERIODS
    name: str
    label: str
    category: str | None
    unit: str | None  # Perhaps enforce no None's?
    moduleName: str
    indexInModule: int | None  # Perhaps enforce no None's?
    isInputVariable: bool
    defaultValue: int | float | bool | str | None
    adds: list[str] | str | None
    subtracts: list[str] | str | None
    hidden_input: bool
    possibleValues: Optional[list[dict[str, Any]]] | None = None
