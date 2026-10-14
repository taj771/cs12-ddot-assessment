# Occupancy permits: FHWA functional class enrichment

Enriches calendar year 2026 Public Space Occupancy Permit locations (DC Water, PEPCO and Washington Gas; Construction Staging Area and Mobile Crane Work Zone permits) with the FHWA functional class of the road at each location, and the highest functional class for each permit.

> Draft. Sections marked *(to do)* are filled in as the work progresses.

## How I approached this

The files in [`enrichment/`](enrichment/) are numbered in the order I worked, so the folder reads as the decision flow.

- **Step 1: explore and check the data.** There is no data dictionary, so I downloaded the whole permit layer with plain `requests` code and looked at it before writing any rules: completeness, dates, permit types, utility names and locations. Each finding became a rule for the steps that follow. See [`step1_explore_layer24.ipynb`](enrichment/step1_explore_layer24.ipynb).

- **Step 2: reusable download helper.** The exploration showed I would need the same download code again (road segments, the road lookup service, the final script), so I moved it into [`step2_rest_client.py`](enrichment/step2_rest_client.py) and added retries for the thousands of road lookups.

- **Steps 3–7: the pipeline.** Filter the permits, match each location to a road segment, look up its functional class, validate the matches, and write the output. *(to do)*

- **Run it** with `enrich_permits.py`, which calls steps 3–7 in order and writes the CSV and a QC summary to `output/`. Some of the checks from step 1 run again on every run, so changes in the source data are flagged rather than silently passed through. *(to do)*

## Key decisions

| Question | Decision | Evidence |
|---|---|---|
| What identifies a permit? | `TrackingNumber` | Always filled. `PermitNumber` is blank on 29% of rows, exactly the rows with no issue date, so it only exists once a permit is issued. |
| Which dates count as 2026? | Application date **or** issue date on/after 1 Jan 2026 | Follows the brief's wording. Adds 7 locations applied for in late 2025 and issued in 2026. |
| Which statuses? | All, with `StatusDescription` in the output | The brief doesn't filter by status, and a rejected or withdrawn application is still an application. The Associate Director can filter on the column. |
| Which permit types? | Exactly "Construction Staging Area" and "Mobile Crane Work Zone" | Both exist with the brief's spelling. No variants. Free-text "Other" rows (2 close matches) are not a reliable category, so they're left out. |
| How to identify the three utilities? | Pattern match on applicant, permittee **or** owner name; output a clean `Utility` column | No utility column exists, and names vary ("DCWater/CIP", "Wash Gas & Light Co.", "Pepco Holdings Inc."). Exact-name matching would miss most. No application names two utilities. Result: 3,102 applications, 4,926 locations. |
| *(more as the exploration continues)* | | |

## How to run *(to do)*

## Output *(to do)*

## Assumptions and limitations *(to do)*

- **Layer 24 only keeps recent permits.** The earliest expiration date in the layer is 30 August 2026, about six weeks before the data was pulled. Older permits appear to be removed from the nightly extract once they expire. The result therefore covers 2026 permits still in the layer on the pull date, and January–August 2026 is heavily undercounted (16 applications in January vs 5,039 in September). No other occupancy permit layer is available in the service.
- **Utility work under other permit types is out of scope.** For example, "Lead Free DC" (DC Water's lead pipe replacement programme, 1,713 rows in 2026) and "Manhole Access" permits are excluded because the brief names the two permit types to use.
