import numpy as np


def get_safe_json(value):
    # This function is used when constructing metadata,
    # which will be consumed by JS, hence Infinity, not .inf
    if isinstance(value, (int, float)):
        if value == np.inf:
            return "Infinity"
        elif value == -np.inf:
            return "-Infinity"
        return value
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        return {k: get_safe_json(v) for k, v in value.items()}
    if isinstance(value, list):
        return [get_safe_json(v) for v in value]
    return None
