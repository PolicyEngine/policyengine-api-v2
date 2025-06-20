from enum import Enum


# Question: Is there a way to instead base these upon COUNTRIES?
# Perhaps build Enum at runtime?
class COUNTRY_ID(Enum):
    US = "us"
    UK = "uk"
    IL = "il"
    CA = "ca"
    NG = "ng"
