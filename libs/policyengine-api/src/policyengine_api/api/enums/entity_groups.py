from enum import Enum


class ENTITY_GROUPS_US(Enum):
    PEOPLE = "people"
    FAMILIES = "families"
    SPM_UNITS = "spm_units"
    TAX_UNITS = "tax_units"
    HOUSEHOLDS = "households"
    MARITAL_UNITS = "marital_units"


class ENTITY_GROUPS_UK(Enum):
    BENUNITS = "benunits"
    PEOPLE = "people"
    HOUSEHOLDS = "households"


class ENTITY_GROUPS_GENERIC(Enum):
    PEOPLE = "people"
    HOUSEHOLDS = "households"
