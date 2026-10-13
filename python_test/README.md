# Occupancy permits: FHWA functional class enrichment

Enriches calendar year 2026 Public Space Occupancy Permit locations (DC Water, PEPCO and Washington Gas; Construction Staging Area and Mobile Crane Work Zone permits) with the FHWA functional class of the road at each location, and the highest functional class for each permit.

> Draft. Sections marked *(to do)* are filled in as the work progresses.

## How I approached this

1. **Built a small download helper.** All data comes from DC's public ArcGIS map services, which return at most 2,000 rows per request. [`enrichment/rest_client.py`](enrichment/rest_client.py) handles paging, retries, error replies, dates and coded values, so every other step can fetch data in one line.

2. **Explored and checked the data.** There is no data dictionary, so I looked at the data before writing any rules: completeness, dates, permit IDs, utility names and locations. Each finding became a rule for the pipeline. See [`notebooks/01_explore_layer24.ipynb`](notebooks/01_explore_layer24.ipynb).

3. **Turned the rules into a pipeline** in [`enrichment/`](enrichment/): filter the permits, match each location to a road segment, look up its functional class, and validate the matches. *(to do)*

4. **Ran it** with `enrich_permits.py`, which writes the CSV and a QC summary to `output/`. Some of the checks from step 2 run again on every run, so changes in the source data are flagged rather than silently passed through. *(to do)*

## Key decisions

| Question | Decision | Evidence |
|---|---|---|
| What identifies a permit? | `TrackingNumber` | Always filled. `PermitNumber` is blank on 29% of rows, exactly the rows with no issue date, so it only exists once a permit is issued. |
| *(more as the exploration continues)* | | |

## How to run *(to do)*

## Output *(to do)*

## Assumptions and limitations *(to do)*
