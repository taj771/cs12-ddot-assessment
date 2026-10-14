"""Step 3: load the 2026 utility occupancy permits from layer 24.

The filtering rules come from step1_explore_layer24.ipynb.
"""

import pandas as pd

import config
from .step2_rest_client import TIMEZONE, fetch_layer

FIELDS = [
    "TrackingNumber", "PermitNumber", "EventTypeDescription", "StatusDescription",
    "ApplicationDate", "IssueDate", "EffectiveDate", "ExpirationDate",
    "ApplicantCompany", "PermitteeName", "OwnerName",
    "WorkLocationFullAddress", "WorkLocationAddressID", "WorkLocationWard", "Quadrant",
    "XCoord", "YCoord",
]
NAME_COLUMNS = ["ApplicantCompany", "PermitteeName", "OwnerName"]


def load_permits():
    """Return one row per permit location for the configured utilities, types and dates."""
    types = ", ".join(f"'{t}'" for t in config.PERMIT_TYPES)
    permits = fetch_layer(
        config.PERMITS_URL,
        where=f"EventTypeDescription IN ({types})",
        fields=",".join(FIELDS),
        geometry=False,
    )

    # Dates are compared in DC time, so this filter is done here rather than on the server (UTC)
    start = pd.Timestamp(config.START_DATE, tz=TIMEZONE)
    in_period = (permits["ApplicationDate"] >= start) | (permits["IssueDate"] >= start)
    permits = permits[in_period].copy()

    permits["Utility"] = find_utility(permits)
    permits = permits[permits["Utility"].notna()].reset_index(drop=True)

    permits["DataPulledAt"] = pd.Timestamp.now(tz=TIMEZONE).floor("s")
    return permits


def find_utility(permits):
    """Name the utility mentioned in any of the company name columns, or NA if none."""
    names = permits[NAME_COLUMNS].fillna("").agg(" | ".join, axis=1)
    utility = pd.Series(pd.NA, index=permits.index, dtype="object")
    for name, pattern in config.UTILITY_PATTERNS.items():
        utility[names.str.contains(pattern, case=False)] = name
    return utility
