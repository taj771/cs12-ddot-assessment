"""Step 5: add the FHWA functional class of each location and the highest class per permit.

The class comes from Roadway SubBlock (layer 162), looked up with the SubBlockKey found
in step 4. FHWA codes run from 1 (Interstate, most important) to 7 (Local, least
important), so "higher class" always means a lower code.

Where step 4 found other segments just as close (an intersection, or a block where the
road's class changes), the higher class is used and the other road is recorded.
"""

import pandas as pd

import config
from .step2_rest_client import fetch_layer

# Number of segment keys per request. Keys are listed in the web address, so
# batches keep the address to a sensible length.
BATCH_SIZE = 100


def add_road_class(permits):
    # Look up every segment step 4 found: the chosen one and any tied with it
    tied_keys = permits["TiedSubBlockKeys"].fillna("").str.split(";").explode()
    keys = pd.concat([permits["SubBlockKey"], tied_keys]).replace("", None).dropna().unique()
    segments = segment_classes(keys).set_index("SubBlockKey")

    # Give each location its class, settling ties by taking the higher class
    settled = permits.apply(lambda row: settle_location(row, segments), axis=1)
    permits = permits.drop(columns=["SubBlockKey", "RoadName", "MatchNote"]).join(settled)

    # For each permit, the most important class among its locations (lowest code)
    highest = permits.groupby("TrackingNumber")["FHWAClassCode"].min()
    permits["HighestFHWAClassCode"] = permits["TrackingNumber"].map(highest)

    # Add the readable name of the highest class, e.g. 4 -> "Minor Arterial"
    names = segments.dropna(subset=["FHWAClassCode"]).drop_duplicates("FHWAClassCode")
    permits["HighestFHWAClass"] = permits["HighestFHWAClassCode"].map(names.set_index("FHWAClassCode")["FHWAClass"])
    return permits


def settle_location(row, segments):
    # All segments at this spot: the one step 4 chose first, then any tied with it
    keys = [row["SubBlockKey"]] + [k for k in str(row["TiedSubBlockKeys"] or "").split(";") if k]
    here = segments.reindex([k for k in keys if pd.notna(k)]).dropna(subset=["RoadName"])
    note = row["MatchNote"]

    # No road segment (nothing found within the search distance): leave the class blank
    if here.empty:
        return pd.Series({"SubBlockKey": None, "RoadName": None, "FHWAClassCode": pd.NA, "FHWAClass": None,
                          "SegmentRoadType": None, "AtIntersection": False, "CrossRoadName": None,
                          "CrossRoadClass": None, "MatchNote": note})

    # Use the tied segment with the highest class (lowest code) if it beats the chosen one
    chosen = here.iloc[0]
    best = here.sort_values("FHWAClassCode", na_position="last").iloc[0]
    if pd.notna(best["FHWAClassCode"]) and (pd.isna(chosen["FHWAClassCode"]) or best["FHWAClassCode"] < chosen["FHWAClassCode"]):
        if best["RoadName"] != chosen["RoadName"]:
            note += "; tie at intersection - higher class used"
        else:
            note += "; class changes here - higher class used"
    else:
        best = chosen

    # Other roads meeting at this spot (a different name means an intersection)
    cross = here[here["RoadName"] != best["RoadName"]].drop_duplicates("RoadName")

    return pd.Series({
        "SubBlockKey": best.name,
        "RoadName": best["RoadName"],
        "FHWAClassCode": best["FHWAClassCode"],
        "FHWAClass": best["FHWAClass"],
        "SegmentRoadType": best["SegmentRoadType"],
        "AtIntersection": not cross.empty,
        "CrossRoadName": "; ".join(cross["RoadName"]) or None,
        "CrossRoadClass": "; ".join(cross["FHWAClass"].fillna("no class")) or None,
        "MatchNote": note,
    })


def segment_classes(keys):
    # Ask layer 162 about the segments, one batch of keys at a time
    batches = []
    for start in range(0, len(keys), BATCH_SIZE):
        key_list = ", ".join(f"'{key}'" for key in keys[start:start + BATCH_SIZE])
        batches.append(fetch_layer(
            config.SUBBLOCKS_URL,
            where=f"SUBBLOCKKEY IN ({key_list})",
            fields="SUBBLOCKKEY,ROUTENAME,ROADTYPE,FHWAFUNCTIONALCLASS",
            geometry=False,
        ))
    segments = pd.concat(batches).drop_duplicates("SUBBLOCKKEY")

    # Keep the key, road name, class code and name, and the segment's road type, with clearer names.
    # The code comes back as a decimal (7.0) when some segments have no class, so make it a whole number.
    segments = segments.rename(columns={
        "SUBBLOCKKEY": "SubBlockKey",
        "ROUTENAME": "RoadName",
        "FHWAFUNCTIONALCLASS": "FHWAClassCode",
        "FHWAFUNCTIONALCLASS_label": "FHWAClass",
        "ROADTYPE_label": "SegmentRoadType",
    })
    segments["RoadName"] = segments["RoadName"].str.split().str.join(" ")  # "INTERSTATE 395   BN" -> "INTERSTATE 395 BN"
    segments["FHWAClassCode"] = segments["FHWAClassCode"].astype("Int64")
    return segments[["SubBlockKey", "RoadName", "FHWAClassCode", "FHWAClass", "SegmentRoadType"]]


if __name__ == "__main__":
    # Quick check, run from the python_test folder: python -m enrichment.step5_road_class
    from .step3_permits import load_permits
    from .step4_road_match import match_roads

    permits = add_road_class(match_roads(load_permits()))

    # How many locations got a class, and which classes
    print(permits["FHWAClass"].value_counts(dropna=False))

    # How the ties were settled
    corners = permits[permits["AtIntersection"]]
    mixed = corners[corners["CrossRoadClass"].ne(corners["FHWAClass"])]
    print(f"\nLocations at an intersection: {len(corners)} (roads of different classes: {len(mixed)})")
    print(f"Class raised at an intersection: {permits['MatchNote'].str.contains('tie at intersection').sum()}")
    print(f"Class raised where the road changes class: {permits['MatchNote'].str.contains('class changes here').sum()}")

    # How many permits cover roads of more than one class
    classes_per_permit = permits.groupby("TrackingNumber")["FHWAClassCode"].nunique()
    print(f"Permits with locations on roads of different classes: {(classes_per_permit > 1).sum()}")

    # Save the table to work/ for checking
    config.WORK_DIR.mkdir(exist_ok=True)
    permits.to_csv(config.WORK_DIR / "step5_road_class.csv", index=False)
