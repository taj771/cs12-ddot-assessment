# Occupancy permits: FHWA functional class enrichment

Enriches calendar year 2026 Public Space Occupancy Permit locations (DC Water, PEPCO and Washington Gas; Construction Staging Area and Mobile Crane Work Zone permits) with the FHWA functional class of the road at each location, and the highest functional class for each permit.

**Result** (data pulled 14 October 2026): 4,983 permit locations from 3,129 applications, in [`output/occupancy_permits_fhwa_2026.csv`](output/occupancy_permits_fhwa_2026.csv). Every location but one has a functional class. 35 locations are flagged for review.

## How to run

Needs Python 3.11 and an internet connection (all data comes from DC's public map services; no API key is needed).

**Windows 11** (Command Prompt, in the `python_test` folder):

```
py -3.11 -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python enrich_permits.py
```

**macOS / Linux:**

```
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python enrich_permits.py
```

The first run takes about 20 minutes, because each permit location is looked up in DDOT's road service and in the address repository. The answers are saved in `cache/`, so later runs take under a minute. Delete `cache/` to look everything up again.

Each step can also be run on its own to check it, e.g. `python -m enrichment.step4_road_match`. It saves its table to `work/`.

**Tests.** `pip install pytest` then `python -m pytest`. The tests cover the matching rules (utility names, address parsing, skipping alleys, corner ties, wider search, highest class per permit, the MAR check) with made-up data, so they run offline in about a second. GitHub runs them on Windows and Linux on every change.

## Output

`output/occupancy_permits_fhwa_2026.csv`, one row per permit location. Dates are in DC local time.

| Columns | What they hold |
|---|---|
| `TrackingNumber`, `PermitNumber` | The application (always filled) and the permit number (only once issued) |
| `Utility`, `EventTypeDescription`, `StatusDescription` | Which utility, permit type, current status |
| `ApplicationDate`, `IssueDate`, `EffectiveDate`, `ExpirationDate` | Permit dates |
| `ApplicantCompany`, `PermitteeName`, `OwnerName` | Names as entered in the permit system |
| `WorkLocationFullAddress`, `WorkLocationWard`, `Quadrant`, `XCoord`, `YCoord` | The location (coordinates in Maryland State Plane, metres) |
| `RoadName`, `SubBlockKey`, `SegmentRoadType`, `DistanceToRoad_m`, `MatchNote` | The road segment the location was matched to, and how |
| `AtIntersection`, `CrossRoadName`, `CrossRoadClass` | The other road, when the location sits where two roads meet |
| **`FHWAClassCode`, `FHWAClass`** | **Functional class of this location** |
| **`HighestFHWAClassCode`, `HighestFHWAClass`** | **Highest functional class across all locations of the application** |
| `NeedsReview`, `ReviewReason`, `MARAddress`, `MARRoadName`, `MARClass` | The check against DC's address repository (see below) |
| `DataPulledAt` | When the permit data was downloaded |

"Highest" means the most important road in the FHWA order: 1 Interstate, 2 Other Freeways and Expressways, 3 Other Principal Arterial, 4 Minor Arterial, 5 Major Collector, 6 Minor Collector, 7 Local. So the smallest code wins.

| Highest class per application | Applications |
|---|---|
| Interstate | 7 |
| Principal Arterial - Other Freeways or Expressways | 2 |
| Principal Arterial - Other | 327 |
| Minor Arterial | 672 |
| Major Collector | 521 |
| Minor Collector | 65 |
| Local | 1,534 |
| No class (no road found) | 1 |

## How I approached this

The files in [`enrichment/`](enrichment/) are numbered in the order I worked, so the folder reads as the decision flow. [`enrich_permits.py`](enrich_permits.py) runs steps 3–7 in order.

1. **Explore the data** ([`step1_explore_layer24.ipynb`](enrichment/step1_explore_layer24.ipynb)). There is no data dictionary, so I downloaded the whole permit layer and looked at it before writing any rules: completeness, dates, permit types, utility names and locations. Each finding became a rule for the later steps.
2. **Download helper** ([`step2_rest_client.py`](enrichment/step2_rest_client.py)). The same download code was needed again for road segments and addresses, so it lives in one place, with paging, retries and readable labels for coded values.
3. **Select the permits** ([`step3_permits.py`](enrichment/step3_permits.py)): the two permit types, 2026 dates, and the three utilities.
4. **Match each location to a road** ([`step4_road_match.py`](enrichment/step4_road_match.py)) with DDOT's road lookup service (`getPointOnSubBlock`), skipping alleys and other non-roads.
5. **Add the functional class** ([`step5_road_class.py`](enrichment/step5_road_class.py)) from the Roadway SubBlock layer, settle corner ties, and work out the highest class per application.
6. **Check the matches** ([`step6_validation.py`](enrichment/step6_validation.py)) against DC's Master Address Repository.
7. **Write the output** ([`step7_output.py`](enrichment/step7_output.py)).

How a location is matched to a road:

```
Search 50 m ─┬─ real road found? ─ yes ─┬─ other segment within 1 m? ─ no ───────── nearest road
             │                          └─ yes ─┬─ same road ──────────────────── nearest road
             │                                  └─ different road (a corner) ──── higher class of the two
             └─ no ─ search 100 m ─┬─ address street in range ─────────────────── address street
                                   ├─ only other roads in range ───────────────── nearest road, marked "check"
                                   └─ no road at all ──────────────────────────── blank
(Alleys, driveways, walkways and trails are ignored at every stage.)
```

## Key decisions

| Question | Decision | Evidence |
|---|---|---|
| What identifies a permit? | `TrackingNumber` | Always filled. `PermitNumber` is blank on 29% of rows, exactly the rows with no issue date, so it only exists once a permit is issued. |
| Which dates count as 2026? | Application date **or** issue date on/after 1 Jan 2026 | Follows the brief's wording ("applications or issued permits"), so a permit applied for in late 2025 and issued in 2026 counts. |
| Which statuses? | All, with `StatusDescription` in the output | The brief doesn't filter by status, and a rejected or withdrawn application is still an application. The column allows filtering. |
| Which permit types? | Exactly "Construction Staging Area" and "Mobile Crane Work Zone" | Both exist with the brief's spelling. No variants. Free-text "Other" rows (2 close matches) are not a reliable category, so they're left out. |
| How to identify the three utilities? | Pattern match on applicant, permittee **or** owner name; output a clean `Utility` column | No utility column exists, and names vary ("DCWater/CIP", "Wash Gas & Light Co.", "Pepco Holdings Inc."). Exact-name matching would miss most. No application names two utilities. |
| Which point to match to a road? | The permit's recorded `XCoord`/`YCoord`, searching within 50 m, with the match distance kept in the output | 99% of points are within 30 m of the street. Using the recorded point avoids relying on the layer's own on-street position, which can't be checked. |
| Repeated locations | Each distinct point is looked up once | 4,983 rows use only 2,605 distinct points. |
| Alleys and other non-roads | Skip alleys, driveways, walkways and trails, and take the nearest real road within 50 m. If there's none, search 100 m and prefer the street named in the address; otherwise take the nearest road and mark it "check" | The brief says to skip alleys, and the other types have no functional class either. Within 50 m the nearest road matches the address street 97% of the time; on the wider search it did only 4 times out of 11, so the address decides there. |
| A point at a corner, where two roads are the same distance away | Use the road with the higher functional class, and record the other road | Roads within 1 m of each other count as a tie. Otherwise the choice would follow the order the road service happens to list them in. 66 locations sit at an intersection, and 16 had their class raised (e.g. Wisconsin Ave × S St NW: Principal Arterial, not Local). |

## Checking the matches

The road lookup picks the road **nearest to the permit point**. To check it another way, step 6 finds the **nearest address** in DC's Master Address Repository (MAR). Every MAR address records the road segment it belongs to. The MAR API needs a key, so the check uses MAR's public address points layer instead.

- On 76% of locations, MAR gives exactly the same road segment, and on a further 6% the same road.
- Where MAR names a different road of a different class, the permit's own address decides who is likely right. Usually it's our match: MAR picked a corner house that faces the cross street (335 locations). On **35 locations** the address agrees with MAR, e.g. 3333 Georgia Ave NW was matched to Morton St (Local), but MAR and the address both say Georgia Ave (Principal Arterial). The permit point sits closer to a side street.
- These 35 rows have `NeedsReview = True` and the suggested road in `ReviewReason`. Their class is **not** changed automatically, because neither source is right every time.

## Assumptions and limitations

- **Layer 24 only keeps recent permits.** The earliest expiration date in the layer is the end of August 2026, about six weeks before the data was pulled. Older permits appear to be removed from the nightly extract once they expire. The result therefore covers 2026 permits still in the layer on the pull date, and January–August 2026 is heavily undercounted. Rerunning later gives a different set of permits.
- **Utility work under other permit types is out of scope.** For example, "Lead Free DC" (DC Water's lead pipe replacement programme) and "Manhole Access" permits are excluded because the brief names the two permit types to use.
- **No utility crane permits in this pull.** All output rows are Construction Staging Area. Layer 24 has Mobile Crane Work Zone applications, but none name DC Water, PEPCO or Washington Gas (their applicants are permit agents and private firms). The crane type stays in the filter as the brief asks.
- **One location has no class.** 1900 Massachusetts Ave SE has no road within 100 m of its point.
- **Ramps count as roads.** At one corner (Washington Ave × 1st St SW) the higher class came from a ramp segment.

## With more time

- A `MatchConfidence` column (high / medium / low) based on how many of the three sources agree: road lookup, MAR address and permit address.
- Use the MAR API (with a key) to look up the permit's address text, which would give a check independent of the permit point.
- A map of the corner locations and the 35 review rows, to see where matching is hardest.
- A scheduled run (e.g. weekly) to keep the output current, since the permit layer drops old permits.
