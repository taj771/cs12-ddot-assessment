"""Settings for the occupancy permit enrichment. Change values here, not in the code."""

from pathlib import Path

# --- Data sources (DC GIS public map services) ---
PERMITS_URL = "https://maps2.dcgis.dc.gov/dcgis/rest/services/DCGIS_APPS/DDOT_TOPS/MapServer/24"
SUBBLOCKS_URL = "https://maps2.dcgis.dc.gov/dcgis/rest/services/DCGIS_DATA/Transportation_WebMercator/MapServer/162"
LRS_URL = (
    "https://rh.dcgis.dc.gov/dcgis/rest/services/DDOT/RoadwayBlocks/MapServer/"
    "exts/DdotLrsExtensions/getPointOnSubBlock"
)

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

# --- Output ---
OUTPUT_DIR = Path(__file__).parent / "output"
CACHE_DIR = Path(__file__).parent / "cache"
