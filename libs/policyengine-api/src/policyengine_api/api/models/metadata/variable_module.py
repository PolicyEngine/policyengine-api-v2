from pydantic import RootModel
from .variable import Variable


class VariableModule(RootModel):
    root: dict[str, Variable]
