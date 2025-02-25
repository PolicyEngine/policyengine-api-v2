from enum import Enum


# Question: Is there a way to instead base these upon COUNTRIES?
# Perhaps build Enum at runtime?
class CountryId(Enum):
    US = "us"
    UK = "uk"
    IL = "il"
    CA = "ca"
    NG = "ng"


class PERIODS(Enum):
    DAY = "day"
    MONTH = "month"
    YEAR = "year"
    ETERNITY = "eternity"


class VALUE_TYPES(Enum):
    BOOL = "bool"
    INT = "int"
    FLOAT = "float"
    STR = "str"
    ENUM = "Enum"
    DATETIME = "datetime.datetime"


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
