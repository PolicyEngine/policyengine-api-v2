from pydantic import BaseModel
from typing import Literal
from policyengine_api.api.utils.constants import PERIODS


# TODO: Answer the below questions
# 1. My first thought on some of these was to import from
# relevant spots (-core, country packages), but converting their
# formats to something viable here seemed difficult at best, flaky
# at worst; however, hand-defining here leaves us open to errors if
# the relevant passage in -core, country package is ever changed
class Variable(BaseModel):
    documentation: str
    entity: str  # Need to modify to be one of a set list
    valueType: str  # Fixed category / enum
    definitionPeriod: Literal[PERIODS]
    name: str
    label: str
    category: str | None
    unit: Literal["currency-GBP", "currency-USD", "currency-EUR", "/1"]
    moduleName: str
    indexInModule: int
    isInputVariable: bool
    defaultValue: int | float | bool | str  # Need to investigate
    adds: list[str] | None
    subtracts: list[str] | None
    hidden_input: bool
    possibleValues: list[dict[str, str]] | None
