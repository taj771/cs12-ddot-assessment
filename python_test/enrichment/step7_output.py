"""Step 7: write the final table, one row per permit location."""

import config

OUTPUT_FILE = config.OUTPUT_DIR / "occupancy_permits_fhwa_2026.csv"

# Final columns, in order: the permit, its location, the road match, the class,
# then the check against MAR
COLUMNS = [
    "TrackingNumber", "PermitNumber", "Utility", "EventTypeDescription", "StatusDescription",
    "ApplicationDate", "IssueDate", "EffectiveDate", "ExpirationDate",
    "ApplicantCompany", "PermitteeName", "OwnerName",
    "WorkLocationFullAddress", "WorkLocationWard", "Quadrant", "XCoord", "YCoord",
    "RoadName", "SubBlockKey", "SegmentRoadType", "DistanceToRoad_m", "MatchNote",
    "AtIntersection", "CrossRoadName", "CrossRoadClass",
    "FHWAClassCode", "FHWAClass", "HighestFHWAClassCode", "HighestFHWAClass",
    "NeedsReview", "ReviewReason", "MARAddress", "MARRoadName", "MARClass",
    "DataPulledAt",
]

DATE_COLUMNS = ["ApplicationDate", "IssueDate", "EffectiveDate", "ExpirationDate", "DataPulledAt"]


def write_output(permits):
    # Keep the final columns, with each permit's locations together
    output = permits[COLUMNS].sort_values(["TrackingNumber", "WorkLocationFullAddress"])

    # Dates in DC time as plain text (e.g. 2026-03-02 09:15) so they open cleanly in Excel
    for column in DATE_COLUMNS:
        output[column] = output[column].dt.strftime("%Y-%m-%d %H:%M")

    config.OUTPUT_DIR.mkdir(exist_ok=True)
    output.to_csv(OUTPUT_FILE, index=False)
    return output


if __name__ == "__main__":
    # Quick check, run from the python_test folder: python -m enrichment.step7_output
    from .step3_permits import load_permits
    from .step4_road_match import match_roads
    from .step5_road_class import add_road_class
    from .step6_validation import validate

    output = write_output(validate(add_road_class(match_roads(load_permits()))))
    print(f"{len(output)} locations, {output['TrackingNumber'].nunique()} applications -> {OUTPUT_FILE}")
    print(output.head(3).T.to_string())
