from policyengine_core.variables import Variable as CoreVariable


def parse_enum_possible_values(
    variable: CoreVariable,
) -> list[dict[str, str]] | None:
    if variable.value_type.__name__ == "Enum":
        return [
            {"value": value.name, "label": value.value}
            for value in variable.possible_values
        ]
    else:
        return None


def parse_default_value(variable: CoreVariable) -> str:
    if variable.value_type.__name__ == "Enum":
        return variable.default_value.name

    if isinstance(variable.default_value, (int, float, bool)):
        return variable.default_value

    return None
