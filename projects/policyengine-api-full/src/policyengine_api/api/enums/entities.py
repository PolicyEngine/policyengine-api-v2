from enum import Enum


class ENTITIES_US(Enum):
    PERSON = "person"
    FAMILY = "family"
    SPM_UNIT = "spm_unit"
    TAX_UNIT = "tax_unit"
    HOUSEHOLD = "household"
    MARITAL_UNIT = "marital_unit"
    STATE = "state"


class ENTITIES_UK(Enum):
    BENUNIT = "benunit"
    PERSON = "person"
    HOUSEHOLD = "household"
    STATE = "state"


class ENTITIES_GENERIC(Enum):
    PERSON = "person"
    HOUSEHOLD = "household"
    STATE = "state"
