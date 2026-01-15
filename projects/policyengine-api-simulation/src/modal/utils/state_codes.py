"""
US state code constants for simulation orchestration.
"""

# Test subset: 10 diverse states (mix of populous and small)
# Populous: TX, NY, FL
# Medium: OH, GA, MA, NV
# Small: NH, VT, MT
TEST_STATE_CODES = [
    "NV",  # Medium - 4 districts
    "TX",  # Large - 38 districts
    "NY",  # Large - 26 districts
    "FL",  # Large - 28 districts
    "OH",  # Medium - 15 districts
    "GA",  # Medium - 14 districts
    "MA",  # Medium - 9 districts
    "NH",  # Small - 2 districts
    "VT",  # Small - 1 district
    "MT",  # Small - 2 districts
]

# All 50 US states + DC (51 total)
STATE_CODES = [
    "AL",
    "AK",
    "AZ",
    "AR",
    "CA",
    "CO",
    "CT",
    "DE",
    "DC",
    "FL",
    "GA",
    "HI",
    "ID",
    "IL",
    "IN",
    "IA",
    "KS",
    "KY",
    "LA",
    "ME",
    "MD",
    "MA",
    "MI",
    "MN",
    "MS",
    "MO",
    "MT",
    "NE",
    "NV",
    "NH",
    "NJ",
    "NM",
    "NY",
    "NC",
    "ND",
    "OH",
    "OK",
    "OR",
    "PA",
    "RI",
    "SC",
    "SD",
    "TN",
    "TX",
    "UT",
    "VT",
    "VA",
    "WA",
    "WV",
    "WI",
    "WY",
]
