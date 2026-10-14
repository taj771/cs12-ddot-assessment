"""Settings for the occupancy permit enrichment. Change values here, not in the code."""

from pathlib import Path

# --- Data sources (DC GIS public map services) ---
PERMITS_URL = "https://maps2.dcgis.dc.gov/dcgis/rest/services/DCGIS_APPS/DDOT_TOPS/MapServer/24"
SUBBLOCKS_URL = "https://maps2.dcgis.dc.gov/dcgis/rest/services/DCGIS_DATA/Transportation_WebMercator/MapServer/162"
LRS_URL = (
    "https://rh.dcgis.dc.gov/dcgis/rest/services/DDOT/RoadwayBlocks/MapServer/"
    "exts/DdotLrsExtensions/getPointOnSubBlock"
)
# DC's Master Address Repository (MAR) address points, used to check the road match
ADDRESSES_URL = "https://maps2.dcgis.dc.gov/dcgis/rest/services/DCGIS_DATA/Location_WebMercator/MapServer/0"

# --- Which permits ---
# A location is kept if it was applied for OR issued on or after this date
START_DATE = "2026-01-01"

PERMIT_TYPES = ["Construction Staging Area", "Mobile Crane Work Zone"]

# Utility names vary a lot in the data ("DCWater/CIP", "Wash Gas & Light Co.",
# "Potomac Electric Power Company"), so each utility is matched by pattern,
# case-insensitive, against the applicant, permittee and owner names.
UTILITY_PATTERNS = {
    "DC Water": r"dc ?water|wasa|water and sewer|water & sewer",
    "PEPCO": r"pepco|potomac electric",
    "Washington Gas": r"washington gas|wash gas|wgl",
}

# --- Matching locations to roads ---
COORDINATE_SYSTEM = 26985   # XCoord/YCoord are in NAD83 / Maryland State Plane (metres)
SEARCH_RADIUS_M = 50        # 99% of permit points are within 30 m of the street
WIDER_SEARCH_RADIUS_M = 100 # second try for the few points with no road within 50 m
TIE_DISTANCE_M = 1          # another road segment this close to the chosen one = same spot (intersection or block boundary)
PARALLEL_LOOKUPS = 5        # road lookups take ~1.5 s each, so run a few at a time

# Segment types with no FHWA functional class. The brief says to skip alleys;
# driveways, walkways and trails give the same blank result, so they are skipped too.
# "Unknown" is how the road service labels a walkway segment (checked against layer 162).
NOT_ROADS = ["Alley", "Driveway", "Walkway", "Trail", "Unknown"]

# --- Checking the matches ---
ADDRESS_SEARCH_RADIUS_M = 50  # look for the nearest MAR address within this distance
FAR_FROM_ROAD_M = 30          # matches further than this from the road are flagged

# --- Output ---
OUTPUT_DIR = Path(__file__).parent / "output"
WORK_DIR = Path(__file__).parent / "work"     # each step's table, for checking (not committed)
CACHE_DIR = Path(__file__).parent / "cache"
