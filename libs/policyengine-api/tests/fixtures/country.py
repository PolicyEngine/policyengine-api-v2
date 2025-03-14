from typing import Any


def is_valid_household(household_dict: dict[str, Any]) -> bool:

    # Surely there must be a better way of doing this, perhaps natively within
    # the Pydantic model itself?
    for entity_group in household_dict.keys():

        # Skip axes; this isn't an entity group, only an info module at the same level
        if entity_group == "axes":
            continue
        for entity in household_dict[entity_group].keys():
            for variable in household_dict[entity_group][entity].keys():
                # Members is an array that can contain any number of items, thus
                # any format is valid
                if variable == "members":
                    continue
                for period in household_dict[entity_group][entity][
                    variable
                ].keys():
                    if (
                        household_dict[entity_group][entity][variable][period]
                        is None
                    ):
                        return False

    return True
