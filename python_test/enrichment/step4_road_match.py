"""Step 4: match each permit location to the nearest real road (not an alley, driveway, walkway or trail).

Uses DDOT's road lookup service (getPointOnSubBlock). Each distinct point is looked
up once, and the answers are saved in cache/ so a rerun doesn't call the service again.
"""

import json
from concurrent.futures import ThreadPoolExecutor, as_completed

import pandas as pd

import config
from .step2_rest_client import get_json

# Saved answers from the road lookup service, one per point
CACHE_FILE = config.CACHE_DIR / "road_matches.json"


def match_roads(permits):
    # Start from the answers saved on earlier runs
    cache = load_cache()
    failed = {}

    # Many permits share the same block, so look up each distinct point only once
    points = permits[["XCoord", "YCoord"]].drop_duplicates()
    todo = [(x, y) for x, y in points.itertuples(index=False) if point_key(x, y) not in cache]
    print(f"{len(points)} distinct points, {len(todo)} to look up")

    # Each lookup takes ~1.5 s, so several run at the same time
    with ThreadPoolExecutor(max_workers=config.PARALLEL_LOOKUPS) as pool:
        lookups = {pool.submit(nearest_road, x, y): point_key(x, y) for x, y in todo}
        for i, lookup in enumerate(as_completed(lookups), start=1):
            key = lookups[lookup]
            try:
                cache[key] = lookup.result()
            except RuntimeError:
                # Not cached, so a rerun tries this point again
                failed[key] = no_match("lookup failed")
            if i % 100 == 0:
                save_cache(cache)
                print(f"  {i} of {len(todo)} done")
    # Save everything once all lookups are finished
    save_cache(cache)

    # Attach the match to every permit location
    answers = {**cache, **failed}
    matches = pd.DataFrame(
        [{"XCoord": x, "YCoord": y, **answers[point_key(x, y)]} for x, y in points.itertuples(index=False)]
    )
    return permits.merge(matches, on=["XCoord", "YCoord"], how="left")


def nearest_road(x, y):
    # Search at the normal distance first. If no real road is found (e.g. a permit
    # in an alley, or on a large site), search once more a little wider.
    road = None
    for radius in (config.SEARCH_RADIUS_M, config.WIDER_SEARCH_RADIUS_M):
        candidates = segments_near(x, y, radius)
        # Alleys, driveways, walkways and trails have no functional class, so skip them
        roads = [c for c in candidates if c["routeType"] not in config.NOT_ROADS]
        if roads:
            road = roads[0]
            break

    if road is None:
        return no_match(f"no road within {config.WIDER_SEARCH_RADIUS_M} m")

    # Note how the road was found: directly, past a nearer non-road segment, or on the wider search
    if radius > config.SEARCH_RADIUS_M:
        note = f"matched on wider search ({radius} m)"
    elif candidates[0]["routeType"] in config.NOT_ROADS:
        note = f"skipped a nearer {candidates[0]['routeType'].lower()}"
    else:
        note = "matched"

    return {
        "SubBlockKey": road["subBlockKey"],
        "RoadName": road["routeName"],
        "RouteType": road["routeType"],
        "DistanceToRoad_m": road["offsetInMeters"],
        "MatchNote": note,
    }


def segments_near(x, y, radius):
    # Ask the road service for all segments within `radius` metres of the point
    params = {
        "x": x,
        "y": y,
        "inSR": config.COORDINATE_SYSTEM,
        "outSR": config.COORDINATE_SYSTEM,
        "searchRadius": radius,
        "f": "json",
    }
    candidates = get_json(config.LRS_URL, params).get("pointOnSubBlocks", [])
    # Nearest segment first (offsetInMeters is the distance from the point)
    return sorted(candidates, key=lambda c: c["offsetInMeters"])


def no_match(reason):
    # An empty answer, with the reason no road was found
    return {"SubBlockKey": None, "RoadName": None, "RouteType": None, "DistanceToRoad_m": None, "MatchNote": reason}


def point_key(x, y):
    # Label for a point in the cache, e.g. "398361.15,134559.55"
    return f"{x},{y}"


def load_cache():
    # Read saved answers, or start empty on the first run
    if CACHE_FILE.exists():
        return json.loads(CACHE_FILE.read_text())
    return {}


def save_cache(cache):
    # Write all answers so far to cache/road_matches.json
    config.CACHE_DIR.mkdir(exist_ok=True)
    CACHE_FILE.write_text(json.dumps(cache))


if __name__ == "__main__":
    # Quick check, run from the python_test folder: python -m enrichment.step4_road_match
    from .step3_permits import load_permits

    permits = match_roads(load_permits())

    # Show how the matching went
    print(permits["MatchNote"].value_counts())
    print(permits["DistanceToRoad_m"].describe().round(1))

    # Save the table to work/ for checking
    config.WORK_DIR.mkdir(exist_ok=True)
    permits.to_csv(config.WORK_DIR / "step4_road_match.csv", index=False)
