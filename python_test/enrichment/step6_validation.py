"""Step 6: flag locations where our road is probably wrong.

Every address in DC's Master Address Repository (MAR) records the road segment it is
on, so the nearest MAR address to a permit point gives a second opinion on the road.
A location is flagged when MAR and the permit's own address both name a different road
with a different class. Flagged rows are not changed.
"""

import json
import math
from concurrent.futures import ThreadPoolExecutor

import pandas as pd

import config
from .step2_rest_client import get_json
from .step4_road_match import point_key, street_in_address
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

    # Flag the rows where MAR and the address both point to another road of another class
    permits["ReviewReason"] = permits.apply(review_reason, axis=1)
    permits["NeedsReview"] = permits["ReviewReason"] != ""
    return permits


def review_reason(row):
    # MAR's road must be a different road with a different class...
    mar_road, mar_class = row["MARRoadName"], row["MARClassCode"]
    if pd.isna(mar_road) or pd.isna(mar_class) or pd.isna(row["FHWAClassCode"]):
        return ""
    if mar_road == row["RoadName"] or mar_class == row["FHWAClassCode"]:
        return ""

    # ...and not the cross road at a corner, which step 5 already compared
    if mar_road in str(row["CrossRoadName"]).split("; "):
        return ""

    # MAR often picks a corner house on the cross street, so its answer alone isn't
    # enough. Flag only when the permit's own address names MAR's road too.
    if mar_road != street_in_address(row["WorkLocationFullAddress"]):
        return ""
    return f"MAR and address say {mar_road} ({row['MARClass']})"


def nearest_addresses(permits):
    # Start from the answers saved on earlier runs, and look up each new point once
    cache = json.loads(CACHE_FILE.read_text(encoding="utf-8")) if CACHE_FILE.exists() else {}
    points = permits.drop_duplicates(["XCoord", "YCoord"])[["XCoord", "YCoord"]]
    todo = [(x, y) for x, y in points.itertuples(index=False) if point_key(x, y) not in cache]
    print(f"{len(points)} distinct points, {len(todo)} to check against MAR")

    # Several lookups at the same time, then save all answers for the next run
    with ThreadPoolExecutor(max_workers=config.PARALLEL_LOOKUPS) as pool:
        for (x, y), answer in zip(todo, pool.map(lambda point: nearest_address(*point), todo)):
            cache[point_key(x, y)] = answer
    config.CACHE_DIR.mkdir(exist_ok=True)
    CACHE_FILE.write_text(json.dumps(cache), encoding="utf-8")

    # One row per point, ready to attach to the permit locations
    return pd.DataFrame(
        [{"XCoord": x, "YCoord": y, **cache[point_key(x, y)]} for x, y in points.itertuples(index=False)]
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
        return {"MARAddress": None, "MARSubBlockKey": None}

    # Keep the closest one (MAR coordinates are in the same metres as the permit points)
    nearest = min(found, key=lambda a: math.dist((x, y), (a["X_COORDINATE"], a["Y_COORDINATE"])))
    return {"MARAddress": nearest["ADDRESS"], "MARSubBlockKey": nearest["SUBBLOCKKEY"]}


if __name__ == "__main__":
    # Quick check, run from the python_test folder: python -m enrichment.step6_validation
    from .step3_permits import load_permits
    from .step4_road_match import match_roads
    from .step5_road_class import add_road_class

    permits = validate(add_road_class(match_roads(load_permits())))

    # The rows to look at, with the reason
    review = permits[permits["NeedsReview"]]
    print(f"Locations needing review: {len(review)} ({review['TrackingNumber'].nunique()} applications)")
    print(review[["WorkLocationFullAddress", "RoadName", "FHWAClass", "ReviewReason"]].to_string())

    # Save the table to work/ for checking
    config.WORK_DIR.mkdir(exist_ok=True)
    permits.to_csv(config.WORK_DIR / "step6_validation.csv", index=False)
