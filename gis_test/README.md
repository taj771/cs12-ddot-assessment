# Roadway SubBlock enrichment: construction permits and service requests

ArcGIS Pro 3.7 project that enriches DDOT's Roadway SubBlock centrelines with excavation and paving permit renewals and open roadway service requests, and creates a version of the permits snapped to the roadway.

**Result** (data pulled 14 October 2026):

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
| **Base and sources** | `RoadwaySubblock` (all enriched blocks) · original permit and request positions · the three REST feeds |

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

The full geoprocessing history is in the project (Catalog → Project → Geoprocessing History). [`pro_steps.md`](pro_steps.md) lists the steps with their settings, and [`notebooks/step1_explore_layers.ipynb`](notebooks/step1_explore_layers.ipynb) is the data exploration the filters come from.

## How I approached it

There is no data dictionary, so I explored the three layers in a notebook first, then ran the geoprocessing in Pro and checked each output against an independent calculation in Python.

```
REST feeds ──filters──► local copies ──► permits: flag alley points, snap to streets (150 m)
                                         requests: snap a copy the same way
                                    ──► link every permit and request to every block it touches (0.5 m)
                                    ──► count per block (permits counted once per block), latest dates
                                    ──► join onto the blocks, flag blocks with both
```

## Key decisions

| Question | Decision | Evidence |
|---|---|---|
| Which permits are renewals? | `Renewal = 2` | `Renewal` is a code with no domain. Every 2 has `RenewalDescription` "Renewal" and every 1 has "New". |
| Which have been issued? | `IssueDate IS NOT NULL` | An issued permit keeps its issue date when its status moves on. 58% of the issued renewals now have the status "Permit Expired", so `StatusDescription = 'Issued'` would drop most of them. |
| Excavation **and** paving? | `IsExcavation = 1 OR IsPaving = 1` | Read as "permits of these two types". Only 132 of 54,625 rows are both. |
| Expiration on or after 1 October 2025 | Kept as given | It removes nothing in this pull: the layer's earliest expiration is August 2026. |
| Service requests | The provided SQL, as given | It matches the brief's statuses (open, pending, inspection completed, which appears as both `INSPCOMP` and `INSPECTION COMPLETED`), except that it also keeps 1 request with status `GEO ISSUE`. |
| Streets, service lanes and ramps | `ROADTYPE IN ('1', '2', '3')` | `ROADTYPE` is a text field. Without the quotes the filter matches nothing. "Service lane" is the "Service Road" code. |
| What does "not snapped to the roadway" mean? | Permits sitting on an **alley or driveway** | The permit points were already placed on a line by DDOT, but 5,038 (27%) of them sit on an alley or driveway instead of a street. Of the 5,046 permits more than 2 m from a street, all but 8 are on an alley or driveway. |
| Snap target and distance | Streets, service roads and ramps only; 150 m | Alleys are not in the snap target, so nothing can snap back to one. The furthest permit was 141 m from a street (large sites such as 3225 Woodley Rd NW). Snap takes the nearest street, so the larger limit doesn't change the other permits. |
| Counting permits per block | Distinct permits (`TrackingNumber`), plus the number of locations | One permit often lists several houses on the same block (e.g. 929–939 Division Ave NE). Counting rows would count that permit several times. |
| A permit or request where two blocks meet | Counted on **every** block it touches | About 1 in 10 permits sits exactly on a junction or block boundary. Assigning it to the nearest block picks one at random and can hide a permit and a request on neighbouring blocks. Counting it on each block found 40 more blocks with both (199 instead of 159). |
| "Touching" a block | Within 0.5 m | Block lines don't meet exactly at junctions (gaps of a few centimetres to about 0.4 m). 0.5 m catches 94% of the junction permits; 1 m adds few more junctions but many points that are only near one. |
| Service requests | Snapped on a copy | Not asked for, but needed so requests and permits are linked to blocks by the same rule. 111 of the 114 off-street requests also sit on an alley. |

## Checks

- After every step I read the geodatabase from outside Pro (Python, `pyogrio` and `shapely`) and recomputed the result independently: row counts, filters, snap distances, block links, every per-block count and date. Everything matched.
- One step didn't match at first: selecting permits near the alleys of the **REST** layer found 2,110 instead of 5,038, because the selection didn't use all the service's features. Redone against a local copy of the alleys, it matched exactly. Spatial selections should run against local data, not live map services.
- All 18,772 snapped permits sit on their street line (distance 0), and each moved exactly the distance measured before snapping.

## Things to know when reading the results

- **Counts add up to more than the number of permits.** The sum of `PermitCount` over all blocks is 7,094, not 3,552, because a permit is counted on each block it touches. The number answers "how many permits affect this block?".
- **Snapping can pick the wrong street.** From an alley, a side street is sometimes closer than the front street. Within 20 m the nearest street matched the permit's address street 94% of the time; beyond 20 m only 51–67%. These permits have `CheckSnap = 'Yes'` (4,260). `Permit_SnapMoves` shows each move.
- **Some work may really be in the alley.** `WasOnAlley = 'Yes'` (5,038) marks the permits DDOT had placed on an alley, so they can be reviewed rather than assumed to be street work.
- **The permit layer only keeps recent permits.** As in the occupancy permit layer, expired permits seem to drop out after a while, so the "expiring on or after 1 October 2025" set is what remains on the pull date.
- **Dates are stored in UTC**, as the services provide them (e.g. 04:00 DC time shows as 08:00).

## With more time

- Use the permit address to choose between near-equal streets when snapping (as in the Python test), for the 4,260 `CheckSnap` permits.
- A short Python script (ArcPy) that reruns the whole workflow, so the result can be refreshed when the feeds change.
- Pop-ups showing only the summary fields instead of all road attributes.
