# Roadway SubBlock enrichment: construction permits and service requests

ArcGIS Pro 3.7 project that enriches DDOT's Roadway SubBlock centrelines with excavation and paving permit renewals and open roadway service requests, and creates a version of the permits snapped to the roadway. Data pulled 14 October 2026.

Code and full history: https://github.com/taj771/cs12-ddot-assessment (this test: [`gis_test/`](https://github.com/taj771/cs12-ddot-assessment/tree/main/gis_test)).

**Result**

| | Blocks |
|---|---|
| Blocks with permits | 4,147 |
| Blocks with open service requests | 673 |
| **Blocks with both** | **199** |

All 18,772 filtered permit locations (3,552 permits) are snapped onto a street, service road or ramp.

## What's in the package

Open `CS12_GIS_Package.ppkx` in ArcGIS Pro 3.x. The map's layers are grouped:

| Group | Layers |
|---|---|
| **Answers to the brief** | `Q3 Blocks with both permits and open requests` (red) · `Q2 Open service requests per block` · `Q1 Permits per block` |
| **Detail: permits and requests** (shown when zoomed in past 1:10,000) | `Permits moved off an alley` · `Permits_Snapped` · `Permit_SnapMoves` (line from each permit's original spot to its snapped spot) · `ServiceRequests_Snapped` |
| **Base and sources** | `RoadwaySubblock` (all enriched blocks) · original permit and request positions · the three REST feeds (live links) |

Geodatabase `CS12_GIS.gdb`:

| Feature class / table | Contents |
|---|---|
| `RoadwaySubblock` | Streets, service roads and ramps (23,104), with `PermitCount`, `PermitLocations`, `PermitMaxExpiration`, `RequestCount`, `RequestMaxInitiated`, `HasPermitAndRequest` |
| `Permits_Filtered` | The filtered permits at their original positions (18,772) |
| `Permits_Snapped` | The same permits snapped to the roadway, with `SnapDistance_m`, `CheckSnap`, `WasOnAlley`, `Orig_X`/`Orig_Y`, and the street each was snapped to (`SUBBLOCKKEY`, `ROUTENAME`) |
| `ServiceRequests_Filtered` / `ServiceRequests_Snapped` | The 692 open service requests, original and snapped |
| `AlleysDriveways` | Alleys and driveways, used to find permits sitting on an alley |
| `Permits_BlockLinks` / `Requests_BlockLinks` | One row per permit (or request) and block it touches |
| `Stats_PermitPerBlock`, `Stats_Permits`, `Stats_Requests` | The summary tables joined onto the blocks |

The geoprocessing history is in the project (Catalog → Project → Geoprocessing History); the steps are listed below. [`notebooks/step1_explore_layers.ipynb`](notebooks/step1_explore_layers.ipynb) is the data exploration the filters come from.

## Approach

There is no data dictionary, so I explored the three layers in a notebook first, then ran the geoprocessing in Pro and checked each output against an independent calculation in Python.

```
1. Filter      Three REST feeds → local copies with only the rows the brief asks for
                   │
2. Snap        Move permits (and a copy of the requests) onto the nearest street
                   │       (about a quarter of the permits were sitting on alleys)
                   │
3. Link        List every block each permit and request touches
                   │       (a point at a junction touches more than one block)
                   │
4. Count       Per block: number of permits and requests, latest dates
                   │
5. Enrich      Write the counts onto the blocks and flag blocks with both
```

## Key decisions

| Question | Decision | Evidence |
|---|---|---|
| Which permits are renewals? | `Renewal = 2` | `Renewal` is a code with no domain. Every 2 has `RenewalDescription` "Renewal", every 1 has "New". |
| Which have been issued? | `IssueDate IS NOT NULL` | An issued permit keeps its issue date when its status moves on. 58% of issued renewals now have the status "Permit Expired", so `StatusDescription = 'Issued'` would drop most of them. |
| Excavation **and** paving? | `IsExcavation = 1 OR IsPaving = 1` | Read as "permits of these two types". Only 132 of 54,625 rows are both. |
| Expiration on or after 1 October 2025 | Kept as given | Removes nothing in this pull: the layer's earliest expiration is August 2026. |
| Service request filter | The brief's SQL, as given | Matches the brief's statuses (open, pending, inspection completed, which appears as both `INSPCOMP` and `INSPECTION COMPLETED`). It also keeps 1 request with status `GEO ISSUE`. |
| Streets, service lanes and ramps | `ROADTYPE IN ('1', '2', '3')` | `ROADTYPE` is a text field; without quotes the filter matches nothing. "Service lane" is the "Service Road" code. |
| What does "not snapped to the roadway" mean? | Permits sitting on an **alley or driveway** | DDOT's feed had already put each permit on a line, but for 5,038 permits (27%) that line is an alley or driveway, not a street. That explains almost all the off-street permits: 5,046 are more than 2 m from a street, and only 8 of those are not on an alley or driveway. |
| Snap target and distance | Streets, service roads and ramps only; 150 m | Alleys are not in the target, so nothing can snap back to one. The furthest permit was 141 m from a street (large sites such as 3225 Woodley Rd NW). Snap takes the nearest street, so the larger limit doesn't change the other permits. |
| Counting permits per block | Distinct permits (`TrackingNumber`), plus the number of locations | One permit often lists several houses on the same block (e.g. 929–939 Division Ave NE). Counting rows would count it several times. |
| A permit or request where two blocks meet | Counted on **every** block it touches | About 1 in 10 permits sits on a junction or block boundary. Nearest-block assignment picks one at random and can hide a permit and a request on neighbouring blocks. Counting on each block found 40 more blocks with both (199 instead of 159). |
| "Touching" a block | Within 0.5 m | Block lines don't meet exactly at junctions (gaps of a few centimetres to about 0.4 m). 0.5 m catches 94% of junction permits; 1 m adds few junctions but many points that are only near one. |
| Snapping the service requests | Done on a copy | Not asked for, but needed so requests and permits are linked to blocks by the same rule. 111 of the 114 off-street requests also sit on an alley. |

## Steps in ArcGIS Pro

All tools were run from the Geoprocessing pane, so they are in the project's history. Counts are from the 14 October pull.

1. New project `CS12_GIS`. Map coordinate system and Analysis → Environments → Output Coordinate System: NAD 1983 StatePlane Maryland FIPS 1900 (Meters), WKID 26985, so distances are true metres.
2. Add Data → Data From Path: the three REST feeds, unfiltered (Roadway Subblock layer 162, DDOT_TOPS Construction Permits layer 23, Cityworks Service Requests layer 1).
3. Export Features with a filter: `RoadwaySubblock` = `ROADTYPE IN ('1','2','3')` (23,104); `Permits_Filtered` = `ExpirationDate >= timestamp '2025-10-01 00:00:00' AND Renewal = 2 AND IssueDate IS NOT NULL AND (IsExcavation = 1 OR IsPaving = 1)` (18,772); `ServiceRequests_Filtered` = the brief's SQL (692).
4. Export Features `Permits_Filtered` → `Permits_Snapped` (Snap edits in place, so the original keeps its positions). Calculate Geometry Attributes: `Orig_X`, `Orig_Y`.
5. Near `Permits_Snapped` → `RoadwaySubblock`, no search radius. Calculate Field: `SnapDistance_m = round(NEAR_DIST, 1)`; `CheckSnap` = Yes where `NEAR_DIST > 20` (4,260).
6. Export Features from the roadway feed → `AlleysDriveways`, `ROADTYPE IN ('4','5')` (11,497). Select Layer By Location: `Permits_Snapped` within 2 m of `AlleysDriveways` (points on a line come out up to about 2 m off it after the feeds are converted from Web Mercator to State Plane). Calculate Field on the selection: `WasOnAlley` = Yes where `NEAR_DIST > 2` (5,038).
7. Snap `Permits_Snapped` to `RoadwaySubblock`, Edge, 150 m. Calculate Geometry Attributes `Snap_X`, `Snap_Y`; select `SnapDistance_m > 2`; XY To Line → `Permit_SnapMoves` (5,046).
8. Export Features `ServiceRequests_Filtered` → `ServiceRequests_Snapped`; Snap to `RoadwaySubblock`, Edge, 150 m (largest move 144.5 m).
9. Near, then Join Field (`NEAR_FID` → `OBJECTID`) to write `SUBBLOCKKEY` and `ROUTENAME` of the nearest street onto the permits and the requests. For reference only; not used for counting.
10. Spatial Join, one-to-many, Intersect, search radius 0.5 m: `Permits_Snapped` → `RoadwaySubblock` = `Permits_BlockLinks` (20,822 rows; 1,812 permits on 2+ blocks); `ServiceRequests_Snapped` → `Requests_BlockLinks` (801; 67 on 2+).
11. Summary Statistics: `Permits_BlockLinks` by `SUBBLOCKKEY_1` + `TrackingNumber`, MAX `ExpirationDate` → `Stats_PermitPerBlock`; then by `SUBBLOCKKEY_1`, COUNT `TrackingNumber`, SUM `FREQUENCY`, MAX of the max date → `Stats_Permits` (4,147). `Requests_BlockLinks` by `SUBBLOCKKEY_1`, COUNT `REQUESTID`, MAX `INITIATEDDATE` → `Stats_Requests` (673).
12. Join Field both stats tables onto `RoadwaySubblock` (`SUBBLOCKKEY` ↔ `SUBBLOCKKEY_1`). Alter Field → `PermitCount`, `PermitLocations`, `PermitMaxExpiration`, `RequestCount`, `RequestMaxInitiated`. Calculate Field: null counts → 0; `HasPermitAndRequest` = Yes where both counts > 0 (199).
13. Map: Make Feature Layer views `Q1 Permits per block` (`PermitCount > 0`, graduated 1 / 2 / 3–5 / 6+), `Q2 Open service requests per block` (`RequestCount > 0`, 1 / 2 / 3+), `Q3 Blocks with both` (red), `Permits moved off an alley` (`WasOnAlley = 'Yes'`). Groups: "Answers to the brief", "Detail: permits and requests (zoom in)" (visible past 1:10,000), "Base and sources".
14. Share → Package Project → `CS12_GIS_Package.ppkx`, with history items; REST layers kept as live links.

## Checks

- After every step I read the geodatabase from outside Pro (Python, `pyogrio` and `shapely`) and recomputed the result independently: row counts, filters, snap distances, block links, every per-block count and date. Everything matched.
- All 18,772 snapped permits sit on their street line (distance 0), and each moved exactly the distance measured before snapping.
- Three steps were redone after a check failed:
  - Selecting permits near the alleys of the **REST** layer found 2,110 instead of 5,038, because the selection didn't use all the service's features. Against the local `AlleysDriveways` copy it matched exactly. Spatial selections should run against local data, not live services.
  - Spatial Join at 0.01 m caught only 217 junction permits, because block ends don't meet exactly. Rerun at 0.5 m.
  - A first enrichment with one block per dot gave 159 blocks with both. Its fields were deleted and replaced with the one-to-many result (199).

## Things to know when reading the results

- **Counts add up to more than the number of permits.** The sum of `PermitCount` over all blocks is 7,094, not 3,552, because a permit is counted on each block it touches. The number answers "how many permits affect this block?".
- **Snapping can pick the wrong street.** From an alley, a side street is sometimes closer than the front street. Within 20 m the nearest street matched the permit's address street 94% of the time; beyond 20 m only 51–67%. These permits have `CheckSnap = 'Yes'` (4,260). `Permit_SnapMoves` shows each move.
- **Some work may really be in the alley.** `WasOnAlley = 'Yes'` (5,038) marks the permits DDOT had placed on an alley, so they can be reviewed rather than assumed to be street work.
- **The permit layer only keeps recent permits.** Expired permits drop out of it: the earliest expiration date in the layer is August 2026, and comparing it with DC's yearly construction permit layers (see the Tableau test) confirms that most permits of the past year are gone. So renewals that expired between October 2025 and August 2026 are missing, and the counts per block are lower than the brief's filter would give on complete data.
- **Dates are stored in UTC**, as the services provide them (e.g. 04:00 DC time shows as 08:00).

## With more time

- Use the permit address to choose between near-equal streets when snapping (as in the Python test), for the 4,260 `CheckSnap` permits.
- A short ArcPy script that reruns the whole workflow, so the result can be refreshed when the feeds change.
- Pop-ups showing only the summary fields instead of all road attributes.
