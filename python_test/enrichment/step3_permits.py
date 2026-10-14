"""Step 3: load the 2026 utility occupancy permits from layer 24.

The filtering rules come from step1_explore_layer24.ipynb.
"""

import re

import pandas as pd

import config
from .step2_rest_client import TIMEZONE, fetch_layer

COLUMNS = [
    "TrackingNumber", "PermitNumber", "EventTypeDescription", "StatusDescription",
    "ApplicationDate", "IssueDate", "EffectiveDate", "ExpirationDate",
    "ApplicantCompany", "PermitteeName", "OwnerName",
    "WorkLocationFullAddress", "WorkLocationAddressID", "WorkLocationWard", "Quadrant",
    "XCoord", "YCoord",
]


def load_permits():
    # Download all permit locations, only the columns we need
    permits = fetch_layer(config.PERMITS_URL, fields=",".join(COLUMNS), geometry=False)

    # Keep the two permit types from the brief
    permits = permits[permits["EventTypeDescription"].isin(config.PERMIT_TYPES)]

    # Keep permits applied for or issued on/after the start date (DC time)
    start = pd.Timestamp(config.START_DATE, tz=TIMEZONE)
    permits = permits[(permits["ApplicationDate"] >= start) | (permits["IssueDate"] >= start)]

    # Keep the three utilities and note which one each permit belongs to
    permits = permits.assign(Utility=permits.apply(find_utility, axis=1))
    permits = permits[permits["Utility"].notna()]

    # The layer drops old permits over time, so record when this copy was taken
    permits = permits.assign(DataPulledAt=pd.Timestamp.now(tz=TIMEZONE).floor("s"))
    return permits


def find_utility(row):
    # Look for a utility name in the applicant, permittee or owner
    names = f"{row['ApplicantCompany']} {row['PermitteeName']} {row['OwnerName']}"
    for utility, pattern in config.UTILITY_PATTERNS.items():
        if re.search(pattern, names, re.IGNORECASE):
            return utility
    return None


if __name__ == "__main__":
    # Quick check, run from the python_test folder: python -m enrichment.step3_permits
    permits = load_permits()
    print(len(permits), "locations,", permits["TrackingNumber"].nunique(), "applications")
    print(permits["Utility"].value_counts())

    config.WORK_DIR.mkdir(exist_ok=True)
    permits.to_csv(config.WORK_DIR / "step3_permits.csv", index=False)
