"""Step 4: match each permit location to the nearest road segment that isn't an alley.

Uses DDOT's road lookup service (getPointOnSubBlock). Each distinct point is looked
up once, and the answers are saved in cache/ so a rerun doesn't call the service again.
"""

import json
from concurrent.futures import ThreadPoolExecutor, as_completed

import pandas as pd

import config
from .step2_rest_client import get_json

CACHE_FILE = config.CACHE_DIR / "road_matches.json"


def match_roads(permits):
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
    save_cache(cache)

    # Attach the match to every permit location
    answers = {**cache, **failed}
    matches = pd.DataFrame(
        [{"XCoord": x, "YCoord": y, **answers[point_key(x, y)]} for x, y in points.itertuples(index=False)]
    )
    return permits.merge(matches, on=["XCoord", "YCoord"], how="left")


def nearest_road(x, y):
    params = {
        "x": x,
        "y": y,
        "inSR": config.COORDINATE_SYSTEM,
        "outSR": config.COORDINATE_SYSTEM,
        "searchRadius": config.SEARCH_RADIUS_M,
        "f": "json",
    }
    candidates = get_json(config.LRS_URL, params).get("pointOnSubBlocks", [])
    candidates.sort(key=lambda c: c["offsetInMeters"])

    # Alleys have no functional class, so skip them (as the brief asks)
    roads = [c for c in candidates if c["routeType"] != "Alley"]
    if not roads:
        return no_match("only alleys nearby" if candidates else "no road within search radius")

    road = roads[0]
    return {
        "SubBlockKey": road["subBlockKey"],
        "RoadName": road["routeName"],
        "RouteType": road["routeType"],
        "DistanceToRoad_m": road["offsetInMeters"],
        "MatchNote": "skipped a nearer alley" if candidates[0]["routeType"] == "Alley" else "matched",
    }


def no_match(reason):
    return {"SubBlockKey": None, "RoadName": None, "RouteType": None, "DistanceToRoad_m": None, "MatchNote": reason}


def point_key(x, y):
    return f"{x},{y}"


def load_cache():
    if CACHE_FILE.exists():
        return json.loads(CACHE_FILE.read_text())
    return {}


def save_cache(cache):
    config.CACHE_DIR.mkdir(exist_ok=True)
    CACHE_FILE.write_text(json.dumps(cache))


if __name__ == "__main__":
    # Quick check, run from the python_test folder: python -m enrichment.step4_road_match
    from .step3_permits import load_permits

    permits = match_roads(load_permits())
    print(permits["MatchNote"].value_counts())
    print(permits["DistanceToRoad_m"].describe().round(1))

    config.WORK_DIR.mkdir(exist_ok=True)
    permits.to_csv(config.WORK_DIR / "step4_road_match.csv", index=False)
