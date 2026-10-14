"""Step 6: check the road matches and flag the rows that need a second look.

The main check uses DC's Master Address Repository (MAR). Every MAR address records
the road segment it is on, so the nearest address to a permit point gives a second
opinion on the road, decided by address rather than by distance. Rows are flagged,
never changed: neither source is right every time.
"""

import json
import math
from concurrent.futures import ThreadPoolExecutor, as_completed

import pandas as pd

import config
from .step2_rest_client import get_json
from .step4_road_match import street_in_address
from .step5_road_class import segment_classes

# Saved answers from the MAR address layer, one per point
CACHE_FILE = config.CACHE_DIR / "mar_addresses.json"


def validate(permits):
    # Find the nearest MAR address to every permit point
    permits = permits.merge(nearest_addresses(permits), on=["XCoord", "YCoord"], how="left")

    # Look up the road name and class of the segment each MAR address is on
    segments = segment_classes(permits["MARSubBlockKey"].dropna().unique()).set_index("SubBlockKey")
    permits["MARRoadName"] = permits["MARSubBlockKey"].map(segments["RoadName"])
    permits["MARClassCode"] = permits["MARSubBlockKey"].map(segments["FHWAClassCode"]).astype("Int64")
    permits["MARClass"] = permits["MARSubBlockKey"].map(segments["FHWAClass"])

    # Compare MAR's road with ours, then list anything that needs a second look
    permits["MARCheck"] = permits.apply(compare_with_mar, axis=1)
    permits["ReviewReason"] = permits.apply(review_reasons, axis=1)
    permits["NeedsReview"] = permits["ReviewReason"] != ""
    return permits


def compare_with_mar(row):
    # No MAR answer to compare with
    if pd.isna(row["MARSubBlockKey"]):
        return row["MARNote"]
    if pd.isna(row["SubBlockKey"]):
        return "no road matched"

    # Same segment, or another block of the same road: the class can be trusted
    if row["MARSubBlockKey"] == row["SubBlockKey"]:
        return "same road segment"
    if row["MARRoadName"] == row["RoadName"]:
        return "same road"

    # At a corner, the nearest address is often on the cross road, which step 5 already compared
    if row["MARRoadName"] in str(row["CrossRoadName"]).split("; "):
        return "cross road at this corner"

    # A different road: only a problem if its class is different too
    if pd.isna(row["MARClassCode"]):
        return "different road, no class (e.g. an alley address)"
    if row["MARClassCode"] == row["FHWAClassCode"]:
        return "different road, same class"
    return "different road, different class"


def review_reasons(row):
    # Every reason to look at this row again, joined into one text
    reasons = []
    if pd.isna(row["FHWAClassCode"]):
        reasons.append("no road class")
    if "- check" in str(row["MatchNote"]):
        reasons.append("wider search, address street not found")
    if row["AtIntersection"] and row["SegmentRoadType"] == "Ramp":
        reasons.append("ramp at corner")
    # MAR often picks a corner house on the cross street, so its answer alone isn't enough.
    # Flag only when the permit's own address names MAR's road and not ours.
    street = street_in_address(row["WorkLocationFullAddress"])
    if row["MARCheck"] == "different road, different class" and row["MARRoadName"] == street != row["RoadName"]:
        reasons.append(f"MAR and address say {row['MARRoadName']} ({row['MARClass']})")
    return "; ".join(reasons)


def nearest_addresses(permits):
    # Start from the answers saved on earlier runs
    cache = load_cache()
    failed = {}

    # Look up each distinct point only once, several at the same time
    points = permits.drop_duplicates(["XCoord", "YCoord"])[["XCoord", "YCoord"]]
    todo = [(x, y) for x, y in points.itertuples(index=False) if point_key(x, y) not in cache]
    print(f"{len(points)} distinct points, {len(todo)} to check against MAR")

    with ThreadPoolExecutor(max_workers=config.PARALLEL_LOOKUPS) as pool:
        lookups = {pool.submit(nearest_address, x, y): point_key(x, y) for x, y in todo}
        for i, lookup in enumerate(as_completed(lookups), start=1):
            key = lookups[lookup]
            try:
                cache[key] = lookup.result()
            except RuntimeError:
                # Not cached, so a rerun tries this point again
                failed[key] = no_address("MAR lookup failed")
            if i % 100 == 0:
                save_cache(cache)
                print(f"  {i} of {len(todo)} done")
    save_cache(cache)

    # One row per point, ready to attach to the permit locations
    answers = {**cache, **failed}
    return pd.DataFrame(
        [{"XCoord": x, "YCoord": y, **answers[point_key(x, y)]} for x, y in points.itertuples(index=False)]
    )


def nearest_address(x, y):
    # Ask the MAR layer for addresses in use within the search distance of the point
    params = {
        "geometry": f"{x},{y}",
        "geometryType": "esriGeometryPoint",
        "inSR": config.COORDINATE_SYSTEM,
        "distance": config.ADDRESS_SEARCH_RADIUS_M,
        "units": "esriSRUnit_Meter",
        "where": "STATUS = 'ACTIVE' AND SUBBLOCKKEY IS NOT NULL",
        "outFields": "ADDRESS,SUBBLOCKKEY,X_COORDINATE,Y_COORDINATE",
        "returnGeometry": "false",
        "f": "json",
    }
    found = [f["attributes"] for f in get_json(f"{config.ADDRESSES_URL}/query", params)["features"]]
    if not found:
        return no_address(f"no MAR address within {config.ADDRESS_SEARCH_RADIUS_M} m")

    # Keep the closest one (MAR coordinates are in the same metres as the permit points)
    def distance(address):
        return math.dist((x, y), (address["X_COORDINATE"], address["Y_COORDINATE"]))

    nearest = min(found, key=distance)
    return {
        "MARAddress": nearest["ADDRESS"],
        "MARSubBlockKey": nearest["SUBBLOCKKEY"],
        "MARDistance_m": round(distance(nearest), 1),
        "MARNote": "nearest address",
    }


def no_address(reason):
    # An empty answer, with the reason no address was found
    return {"MARAddress": None, "MARSubBlockKey": None, "MARDistance_m": None, "MARNote": reason}


def qc_summary(permits):
    # A short text report of how the run went, saved next to the output
    lines = [
        f"Data pulled: {permits['DataPulledAt'].iloc[0]}",
        f"Permit locations: {len(permits)}  Applications: {permits['TrackingNumber'].nunique()}",
        "",
        "How each location was matched to a road:",
        permits["MatchNote"].value_counts().to_string(),
        "",
        f"Locations at an intersection: {permits['AtIntersection'].sum()}",
        "",
        "Check against MAR (nearest address's road vs our road):",
        (permits["MARCheck"].value_counts(normalize=True) * 100).round(1).astype(str).add(" %").to_string(),
        "",
        f"Locations needing review: {permits['NeedsReview'].sum()} "
        f"({permits.loc[permits['NeedsReview'], 'TrackingNumber'].nunique()} applications)",
    ]
    # How often each reason comes up (a row can have more than one)
    for reason in ["no road class", "wider search", "ramp at corner", "MAR and address"]:
        lines.append(f"  {reason}: {permits['ReviewReason'].str.contains(reason).sum()}")
    return "\n".join(lines)


def point_key(x, y):
    # Label for a point in the cache, e.g. "398361.15,134559.55"
    return f"{x},{y}"


def load_cache():
    # Read saved answers, or start empty on the first run
    if CACHE_FILE.exists():
        return json.loads(CACHE_FILE.read_text())
    return {}


def save_cache(cache):
    # Write all answers so far to cache/mar_addresses.json
    config.CACHE_DIR.mkdir(exist_ok=True)
    CACHE_FILE.write_text(json.dumps(cache))


if __name__ == "__main__":
    # Quick check, run from the python_test folder: python -m enrichment.step6_validation
    from .step3_permits import load_permits
    from .step4_road_match import match_roads
    from .step5_road_class import add_road_class

    permits = validate(add_road_class(match_roads(load_permits())))
    print(qc_summary(permits))

    # The rows to look at, with the reason
    review = permits[permits["NeedsReview"]]
    print(review[["WorkLocationFullAddress", "RoadName", "FHWAClass", "ReviewReason"]].head(15).to_string())

    # Save the table to work/ for checking
    config.WORK_DIR.mkdir(exist_ok=True)
    permits.to_csv(config.WORK_DIR / "step6_validation.csv", index=False)
