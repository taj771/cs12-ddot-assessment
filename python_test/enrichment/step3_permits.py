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
    # Download every permit location in the layer, keeping only the columns we use
    permits = fetch_layer(config.PERMITS_URL, fields=",".join(FIELDS), geometry=False)

    # Keep the two permit types named in the brief
    is_permit_type = permits["EventTypeDescription"].isin(config.PERMIT_TYPES)

    # Keep permits applied for or issued from the start date on (compared in DC time)
    start = pd.Timestamp(config.START_DATE, tz=TIMEZONE)
    is_in_period = (permits["ApplicationDate"] >= start) | (permits["IssueDate"] >= start)

    permits = permits[is_permit_type & is_in_period].copy()

    # Keep only permits from the three utilities, and record which one
    permits["Utility"] = find_utility(permits)
    permits = permits[permits["Utility"].notna()].reset_index(drop=True)

    # The layer drops old permits over time, so note when this copy was taken
    permits["DataPulledAt"] = pd.Timestamp.now(tz=TIMEZONE).floor("s")
    return permits


def find_utility(permits):
    """Name the utility mentioned in any of the company name columns, or NA if none."""
    names = permits[NAME_COLUMNS].fillna("").agg(" | ".join, axis=1)
    utility = pd.Series(pd.NA, index=permits.index, dtype="object")
    for name, pattern in config.UTILITY_PATTERNS.items():
        utility[names.str.contains(pattern, case=False)] = name
    return utility


if __name__ == "__main__":
    # Quick check from the python_test folder:  python -m enrichment.step3_permits
    permits = load_permits()
    print(f"{len(permits):,} locations, {permits['TrackingNumber'].nunique():,} applications")
    print(permits.groupby("Utility")["TrackingNumber"].agg(locations="size", applications="nunique"))

    config.WORK_DIR.mkdir(exist_ok=True)
    permits.to_csv(config.WORK_DIR / "step3_permits.csv", index=False)
    print(f"Saved to {config.WORK_DIR / 'step3_permits.csv'}")
