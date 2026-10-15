"""Build the data files for the Tableau workbook on FY26 construction permit approval times.

Run from the tableau_test folder:  python scripts/prepare_data.py
Writes four CSV files to prepared_data/. The rules come from
notebooks/step1_explore_permits.ipynb.
"""

import re
from pathlib import Path

import holidays
import numpy as np
import pandas as pd
import requests

PERMITS_23 = "https://maps2.dcgis.dc.gov/dcgis/rest/services/DCGIS_APPS/DDOT_TOPS/MapServer/23"
YEARLY_LAYERS = [  # DC's yearly construction permit layers, which keep every permit of the year
    "https://maps2.dcgis.dc.gov/dcgis/rest/services/FEEDS/DDOT/FeatureServer/46",  # 2025
    "https://maps2.dcgis.dc.gov/dcgis/rest/services/FEEDS/DDOT/FeatureServer/48",  # 2026
]

TIMEZONE = "America/New_York"
FY26_START = pd.Timestamp("2025-10-01", tz=TIMEZONE)
FY27_START = pd.Timestamp("2026-10-01", tz=TIMEZONE)
# Layer 23 drops permits once they expire. From July 2026 on it still holds almost all of them.
COMPLETE_FROM = pd.Timestamp("2026-07-01", tz=TIMEZONE)

OUTPUT_DIR = Path(__file__).resolve().parent.parent / "prepared_data"

# DC public holidays: US federal holidays plus D.C. Emancipation Day (16 April), with
# weekend holidays moved to the observed weekday. Checked against DC's official list
# for 2026 (edpm.dc.gov/issuances/legal-public-holidays).
DC_HOLIDAYS = holidays.US(subdiv="DC", years=[2025, 2026])
HOLIDAY_DATES = np.array(sorted(DC_HOLIDAYS), dtype="datetime64[D]")


def download(layer_url, where="1=1", fields="*"):
    # All rows matching `where`, page by page (the services return at most 2,000 per request)
    rows, offset = [], 0
    while True:
        params = {"where": where, "outFields": fields, "returnGeometry": "false", "orderByFields": "OBJECTID",
                  "resultOffset": offset, "resultRecordCount": 2000, "f": "json"}
        page = requests.get(f"{layer_url}/query", params=params, timeout=120).json()
        if "error" in page:
            raise RuntimeError(page["error"])
        rows += [feature["attributes"] for feature in page["features"]]
        if not page.get("exceededTransferLimit"):
            return pd.DataFrame(rows)
        offset += len(page["features"])


def to_dc_time(values, already_local=False):
    # Dates arrive as milliseconds since 1970. Layer 23 sends UTC; the yearly layers send
    # DC local time labelled as UTC, so those are read as local time directly.
    dates = pd.to_datetime(values, unit="ms")
    if already_local:
        return dates.dt.tz_localize(TIMEZONE, ambiguous="NaT", nonexistent="shift_forward")
    return dates.dt.tz_localize("UTC").dt.tz_convert(TIMEZONE)


def business_days(start, end):
    # Working days from start to end, skipping weekends and DC holidays.
    # Same day = 0, next working day = 1. Blank where either date is missing.
    known = start.notna() & end.notna()
    days = pd.Series(np.nan, index=start.index)
    days[known] = np.busday_count(start[known].dt.date.values.astype("datetime64[D]"),
                                  end[known].dt.date.values.astype("datetime64[D]"),
                                  holidays=HOLIDAY_DATES)
    return days


def work_type(excavation, paving, fixture, overhead):
    # Level 1 permit category from the work-type flags (the yearly layers have no overhead flag)
    types = [name for flag, name in [(excavation, "Excavation"), (paving, "Paving"), (fixture, "Fixture"),
                                     (overhead, "Overhead work")] if flag]
    if len(types) > 1:
        return "Multiple types"
    return types[0] if types else "Other (projections, landscaping, rental)"


def excavation_for(work_items):
    # Level 2 for excavation permits: which utility the work is for, from the work item names
    text = str(work_items).lower()
    found = [name for name, words in [("Gas", "gas"), ("Water", "water|hydrant|valve"), ("Sewer", "sewer|clean out"),
                                      ("Electric", "electric|conduit|cathodic"), ("Telecom", "telecom|fiber|cable"),
                                      ("Test pits", "boring|test pit")] if re.search(words, text)]
    if len(found) > 1:
        return "Several utilities"
    return found[0] if found else "Other excavation"


def applicant(names):
    # Who the permit is for, from the permittee, applicant and owner names
    names = names.lower()
    for group, pattern in [("Washington Gas", r"wash gas|washington gas|wgl"), ("DC Water", r"dc ?water|wasa"),
                           ("PEPCO", r"pepco|potomac electric"),
                           ("Telecom", r"verizon|comcast|zayo|crown castle|at&t|lumen|cogent|rcn"),
                           ("DC government", r"department|district of columbia|ddot|doee|public schools|office of")]:
        if re.search(pattern, names):
            return group
    return "Private / other"


def approvals():
    # New permits applied for in FY26 and approved by 30 September 2026, one row per permit (layer 23)
    rows = download(PERMITS_23, where="Renewal = 1 AND ApplicationDate >= timestamp '2025-10-01 00:00:00'")
    locations = rows.groupby("TrackingNumber").size()
    permits = rows.drop_duplicates("TrackingNumber").copy()
    for column in ["ApplicationDate", "ReadyForReviewDate", "LastApprovalDate", "IssueDate", "LastResubmissionRequestDate"]:
        permits[column] = to_dc_time(permits[column])
    permits = permits[permits["LastApprovalDate"].notna() & (permits["LastApprovalDate"] < FY27_START)]

    # Business days for each stage
    permits["DaysToApprove"] = business_days(permits["ApplicationDate"], permits["LastApprovalDate"])
    permits["DaysToReadyForReview"] = business_days(permits["ApplicationDate"], permits["ReadyForReviewDate"])
    permits["DaysApprovalToIssue"] = business_days(permits["LastApprovalDate"], permits["IssueDate"])

    # Which permits count for the brief (issued in FY26) and which months are complete in this layer
    permits["IssuedInFY26"] = (permits["IssueDate"] >= FY26_START) & (permits["IssueDate"] < FY27_START)
    permits["CompletePeriod"] = permits["ApplicationDate"] >= COMPLETE_FROM

    # Categories and splits
    permits["WorkType"] = [work_type(*flags) for flags in
                           permits[["IsExcavation", "IsPaving", "IsFixture", "IsOverHeadWork"]].eq(1).values]
    permits["ExcavationFor"] = np.where(permits["WorkType"] == "Excavation",
                                        permits["TypeDetailNames"].map(excavation_for), None)
    permits["Applicant"] = (permits["PermitteeName"].fillna("") + " " + permits["ApplicantCompany"].fillna("")
                            + " " + permits["OwnerName"].fillna("")).map(applicant)
    permits["ResubmissionRequested"] = permits["LastResubmissionRequestDate"].notna().map({True: "Yes", False: "No"})
    permits["Locations"] = permits["TrackingNumber"].map(locations)
    permits["LocationsGroup"] = pd.cut(permits["Locations"], [0, 1, 3, 10, 10_000],
                                       labels=["1", "2–3", "4–10", "11 or more"]).astype(str)
    permits["AppliedMonth"] = permits["ApplicationDate"].dt.strftime("%Y-%m")

    columns = ["TrackingNumber", "PermitNumber", "StatusDescription", "ApplicationDate", "ReadyForReviewDate",
               "LastApprovalDate", "IssueDate", "AppliedMonth", "DaysToApprove", "DaysToReadyForReview",
               "DaysApprovalToIssue", "IssuedInFY26", "CompletePeriod", "WorkType", "ExcavationFor", "Applicant",
               "ResubmissionRequested", "Locations", "LocationsGroup", "WorkLocationWard"]
    return permits[columns]


def full_year():
    # All new permits applied for and issued in FY26, from the yearly layers, one row per permit
    fields = ("TRACKINGNUMBER,PERMITNUMBER,APPLICATIONDATE,ISSUEDATE,ISEXCAVATION,ISPAVING,ISFIXTURE")
    where = "APPLICATIONDATE >= timestamp '2025-10-01 00:00:00'"
    permits = pd.concat([download(url, where, fields) for url in YEARLY_LAYERS]).drop_duplicates("TRACKINGNUMBER")
    for column in ["APPLICATIONDATE", "ISSUEDATE"]:
        permits[column] = to_dc_time(permits[column], already_local=True)

    # New permits only: renewal permit numbers end in "-R1", "-R2"... (checked against layer 23)
    is_new = permits["PERMITNUMBER"].notna() & ~permits["PERMITNUMBER"].str.contains(r"-R\d*$", na=False)
    issued_fy26 = (permits["ISSUEDATE"] >= FY26_START) & (permits["ISSUEDATE"] < FY27_START)
    permits = permits[is_new & issued_fy26].copy()

    permits["DaysToIssue"] = business_days(permits["APPLICATIONDATE"], permits["ISSUEDATE"])
    permits["WorkType"] = [work_type(*flags, False) for flags in
                           permits[["ISEXCAVATION", "ISPAVING", "ISFIXTURE"]].eq("T").values]
    permits["AppliedMonth"] = permits["APPLICATIONDATE"].dt.strftime("%Y-%m")
    permits = permits.rename(columns={"TRACKINGNUMBER": "TrackingNumber", "PERMITNUMBER": "PermitNumber",
                                      "APPLICATIONDATE": "ApplicationDate", "ISSUEDATE": "IssueDate"})
    return permits[["TrackingNumber", "PermitNumber", "ApplicationDate", "IssueDate", "AppliedMonth",
                    "DaysToIssue", "WorkType"]]


def completeness(full, approved):
    # For each application month: all new FY26 permits vs those still in layer 23
    in_layer_23 = full["TrackingNumber"].astype(str).isin(approved["TrackingNumber"].astype(str))
    table = full.assign(InLayer23=in_layer_23).groupby("AppliedMonth").agg(
        AllPermits=("TrackingNumber", "size"), StillInLayer23=("InLayer23", "sum")).reset_index()
    table["Coverage"] = (table["StillInLayer23"] / table["AllPermits"]).round(3)
    return table


if __name__ == "__main__":
    OUTPUT_DIR.mkdir(exist_ok=True)

    approved = approvals()
    full = full_year()
    coverage = completeness(full, approved[approved["IssuedInFY26"]])
    # The holidays inside FY26, so the workbook can list the days that were skipped
    fy26_days = [day for day in sorted(DC_HOLIDAYS) if FY26_START.date() <= day < FY27_START.date()]
    holiday_table = pd.DataFrame({"Date": [str(day) for day in fy26_days],
                                  "Holiday": [DC_HOLIDAYS[day] for day in fy26_days]})

    approved.to_csv(OUTPUT_DIR / "fy26_approvals.csv", index=False)
    full.to_csv(OUTPUT_DIR / "fy26_days_to_issue.csv", index=False)
    coverage.to_csv(OUTPUT_DIR / "fy26_completeness.csv", index=False)
    holiday_table.to_csv(OUTPUT_DIR / "dc_holidays.csv", index=False)

    # Quick check of the headline numbers
    brief = approved[approved["IssuedInFY26"] & approved["CompletePeriod"]]
    print(f"Approvals file: {len(approved):,} permits; counted for the brief in the complete period: {len(brief):,}")
    print(f"  Business days to approve: average {brief['DaysToApprove'].mean():.1f}, median {brief['DaysToApprove'].median():.0f}")
    print(f"Days-to-issue file: {len(full):,} permits; average {full['DaysToIssue'].mean():.1f} business days")
    print(f"Files written to {OUTPUT_DIR}")
