"""Step 5: add the FHWA functional class of each location and the highest class per permit.

The class comes from Roadway SubBlock (layer 162), looked up with the SubBlockKey found
in step 4. FHWA codes run from 1 (Interstate, most important) to 7 (Local, least
important), so a permit's highest class is the lowest code among its locations.
"""

import pandas as pd

import config
from .step2_rest_client import fetch_layer

# Number of segment keys per request. Keys are listed in the web address, so
# batches keep the address to a sensible length.
BATCH_SIZE = 100


def add_road_class(permits):
    # Look up the class of every road segment that step 4 matched
    keys = permits["SubBlockKey"].dropna().unique()
    segments = segment_classes(keys)

    # Give every location the class of its road segment.
    # Locations with no segment (no road within the search radius) stay blank.
    permits = permits.merge(segments, on="SubBlockKey", how="left")

    # For each permit, the most important class among its locations (lowest code)
    highest = permits.groupby("TrackingNumber")["FHWAClassCode"].min()
    permits["HighestFHWAClassCode"] = permits["TrackingNumber"].map(highest)

    # Add the readable name of the highest class, e.g. 4 -> "Minor Arterial"
    names = segments.dropna().drop_duplicates("FHWAClassCode").set_index("FHWAClassCode")["FHWAClass"]
    permits["HighestFHWAClass"] = permits["HighestFHWAClassCode"].map(names)
    return permits


def segment_classes(keys):
    # Ask layer 162 about the segments, one batch of keys at a time
    batches = []
    for start in range(0, len(keys), BATCH_SIZE):
        key_list = ", ".join(f"'{key}'" for key in keys[start:start + BATCH_SIZE])
        batches.append(fetch_layer(
            config.SUBBLOCKS_URL,
            where=f"SUBBLOCKKEY IN ({key_list})",
            fields="SUBBLOCKKEY,ROADTYPE,FHWAFUNCTIONALCLASS",
            geometry=False,
        ))
    segments = pd.concat(batches).drop_duplicates("SUBBLOCKKEY")

    # Keep the key, the class code and name, and the segment's road type, with clearer names.
    # The code comes back as a decimal (7.0) when some segments have no class, so make it a whole number.
    segments = segments.rename(columns={
        "SUBBLOCKKEY": "SubBlockKey",
        "FHWAFUNCTIONALCLASS": "FHWAClassCode",
        "FHWAFUNCTIONALCLASS_label": "FHWAClass",
        "ROADTYPE_label": "SegmentRoadType",
    })
    segments["FHWAClassCode"] = segments["FHWAClassCode"].astype("Int64")
    return segments[["SubBlockKey", "FHWAClassCode", "FHWAClass", "SegmentRoadType"]]


if __name__ == "__main__":
    # Quick check, run from the python_test folder: python -m enrichment.step5_road_class
    from .step3_permits import load_permits
    from .step4_road_match import match_roads

    permits = add_road_class(match_roads(load_permits()))

    # How many locations got a class, and which classes
    print(permits["FHWAClass"].value_counts(dropna=False))

    # Which kinds of segment ended up with no class
    no_class = permits[permits["FHWAClassCode"].isna()]
    print("\nLocations with no class, by segment type:")
    print(no_class["SegmentRoadType"].value_counts(dropna=False))

    # How many permits cover roads of more than one class
    classes_per_permit = permits.groupby("TrackingNumber")["FHWAClassCode"].nunique()
    print(f"\nPermits with locations on roads of different classes: {(classes_per_permit > 1).sum()}")

    # Save the table to work/ for checking
    config.WORK_DIR.mkdir(exist_ok=True)
    permits.to_csv(config.WORK_DIR / "step5_road_class.csv", index=False)
