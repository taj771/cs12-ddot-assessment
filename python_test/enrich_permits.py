"""Enrich the 2026 utility occupancy permits with the FHWA functional class of each location.

Run from this folder:  python enrich_permits.py
Writes output/occupancy_permits_fhwa_2026.csv. The first run takes about 20 minutes
(thousands of road and address lookups); later runs reuse the saved answers in cache/.
"""

from enrichment.step3_permits import load_permits
from enrichment.step4_road_match import match_roads
from enrichment.step5_road_class import add_road_class
from enrichment.step6_validation import validate
from enrichment.step7_output import OUTPUT_FILE, write_output

# Step 3: download the permit locations and keep the 2026 utility permits
permits = load_permits()
print(f"Permits: {len(permits)} locations, {permits['TrackingNumber'].nunique()} applications")

# Step 4: match each location to the nearest real road
permits = match_roads(permits)
print(f"Matched to a road: {permits['SubBlockKey'].notna().sum()} locations")

# Step 5: add the functional class of each location and the highest class per permit
permits = add_road_class(permits)
print(f"With a functional class: {permits['FHWAClassCode'].notna().sum()} locations")

# Step 6: check the roads against the nearest MAR address
permits = validate(permits)
print(f"Flagged for review: {permits['NeedsReview'].sum()} locations")

# Step 7: save the final table
write_output(permits)
print(f"Saved {OUTPUT_FILE}")
