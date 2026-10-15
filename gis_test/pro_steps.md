# GIS test: steps in ArcGIS Pro

The order of geoprocessing in ArcGIS Pro 3.7, with the settings used. The filters and settings come from the exploration notebook ([`notebooks/step1_explore_layers.ipynb`](notebooks/step1_explore_layers.ipynb)). All tools are run from the Geoprocessing pane so they appear in the project's geoprocessing history.

Expected counts (pull of 14 October 2026) are given after each step as a check. They change a little from day to day, because the source layers update nightly.

## 0. Project setup

1. New project **CS12_GIS** (Map template). It creates `CS12_GIS.gdb`, which is the default geodatabase.
2. Map properties → Coordinate Systems: **NAD 1983 StatePlane Maryland FIPS 1900 (Meters)** (WKID 26985). This is DC's local system in metres, so snap and search distances are true metres.
3. Analysis → Environments: **Output Coordinate System** = same as the map (26985), so every exported layer is in metres.

## 1. Add the REST feeds (unfiltered)

Map → Add Data → Data From Path, one at a time:

| Layer name in the map | URL |
|---|---|
| Construction Permits (REST) | `https://maps2.dcgis.dc.gov/dcgis/rest/services/DCGIS_APPS/DDOT_TOPS/MapServer/23` |
| Cityworks Service Requests (REST) | `https://maps2.dcgis.dc.gov/dcgis/rest/services/DDOT/Cityworks/MapServer/1` |
| Roadway Subblock (REST) | `https://maps2.dcgis.dc.gov/dcgis/rest/services/DCGIS_DATA/Transportation_WebMercator/MapServer/162` |

These stay as live feeds, as the brief asks. The local copies below are made from them.

## 2. Local copies with the filters

**Export Features** (Conversion), once per layer, with the filter in *Filter* / *Expression* (SQL mode):

| Input | Output | Expression | Expected |
|---|---|---|---|
| Roadway Subblock (REST) | `RoadwaySubblock` | `ROADTYPE IN ('1', '2', '3')` | 23,104 |
| Construction Permits (REST) | `Permits_Filtered` | `ExpirationDate >= timestamp '2025-10-01 00:00:00' AND Renewal = 2 AND IssueDate IS NOT NULL AND (IsExcavation = 1 OR IsPaving = 1)` | 18,772 |
| Cityworks Service Requests (REST) | `ServiceRequests_Filtered` | `STATUS NOT IN ('CLOSED', 'CANCEL', 'COMPLETE') And DESCRIPTION IN ('ROADWAY REPAIR', 'POTHOLES', 'STREET REPAVING', 'STREET REPAIR', 'STREET PAVING SCHEDU') And INITIATEDDATE >= timestamp '2025-10-01 00:00:00'` | 692 |

Notes from the exploration:
- `ROADTYPE` is a text field, so the codes need quotes. Without them nothing matches.
- `Renewal = 2` is Renewal (1 is New).
- "Issued" = has an issue date. Most issued renewals now have the status "Permit Expired", so a status filter would drop them.

Check the row counts (attribute table or Get Count) before going on.

## 3. Prepare the permits for snapping

Snap moves the features of its input in place, so snapping is done on a copy and `Permits_Filtered` keeps the original positions.

1. **Export Features**: `Permits_Filtered` → `Permits_Snapped` (no filter).
2. **Calculate Geometry Attributes** on `Permits_Snapped`: new fields `Orig_X` = Point x-coordinate, `Orig_Y` = Point y-coordinate. This keeps where each permit started.
3. **Near** (Analysis): input `Permits_Snapped`, near features `RoadwaySubblock`, no search radius. It adds `NEAR_DIST` = how far each permit is from the nearest street, service road or ramp, which is how far the snap will move it.
4. **Add Field** + **Calculate Field** on `Permits_Snapped`:
   - `SnapDistance_m` (Double) = `!NEAR_DIST!`
   - `WasOnAlley` (Text 3): `Yes` where the permit sits on an alley or driveway, otherwise `No`. To set it:
     - Make a layer from **Roadway Subblock (REST)** with the definition query `ROADTYPE IN ('4', '5')` (alleys and driveways), named *Alleys and driveways (REST)*.
     - **Select Layer By Location**: `Permits_Snapped` that are **within a distance** of *Alleys and driveways (REST)*, 2 Meters. (Points that sit on a line come out up to about 2 m off it after the feeds are converted from Web Mercator to our metre system, so 2 m is the tolerance for "on a line".)
     - Calculate `WasOnAlley` = `"Yes"` on the selection. Then **Select Layer By Attribute**, switch the selection, and calculate `"No"`. Then clear the selection.
   - `CheckSnap` (Text 3) = `Yes` when `SnapDistance_m > 20`, otherwise `No`. Beyond 20 m the nearest street is less often the address street (51–67% in the sample vs 94% within 20 m).

   Expected: about a third of permits have `WasOnAlley = Yes`.

## 4. Snap the permits to the roadway

**Snap** (Editing):
- Input features: `Permits_Snapped`
- Snap environment: `RoadwaySubblock`, Type **Edge**, Distance **150 Meters**

The Near step showed 11 permits 73–141 m from any street (large sites such as 3225 Woodley Rd NW), so 150 m makes sure every permit lands on a street. Snap always takes the nearest street, so the distance limit doesn't change where the other permits go. Permits already on a street don't move, and alleys aren't in `RoadwaySubblock`, so nothing can snap to an alley.

Check: **Near** again on `Permits_Snapped` → `NEAR_DIST` should now be 0 (or a few millimetres) for all permits.

Optional, for exploring: **XY To Line** (Data Management) from `Permits_Snapped`, start `Orig_X`/`Orig_Y`, end = the snapped position (first add `Snap_X`/`Snap_Y` with Calculate Geometry Attributes) → `Permit_SnapMoves`. One short line per permit that moved, showing where it jumped from.

## 5. Find the road segment of each permit and request

**Spatial Join** (Analysis), one-to-one, keep all target features, match option **Closest**:

| Target | Join features | Search radius | Output |
|---|---|---|---|
| `Permits_Snapped` | `RoadwaySubblock` | 1 Meters | `Permits_Snapped_Block` |
| `ServiceRequests_Filtered` | `RoadwaySubblock` | 70 Meters | `ServiceRequests_Block` |

In the field map, keep the input fields plus `SUBBLOCKKEY` (and `ROUTENAME` for reading). Spatial Join adds `Distance` for the Closest option, which shows how far each request is from its block.

`Permits_Snapped_Block` is the snapped permit deliverable (snapped points + their block).

## 6. Counts and latest dates per block

Permits are counted as **distinct permits** per block, because one permit often lists several houses on the same block. So two Summary Statistics steps:

1. **Summary Statistics**: input `Permits_Snapped_Block`; statistics `ExpirationDate` MAX; case fields `SUBBLOCKKEY`, `TrackingNumber` → `Stats_PermitPerBlock` (one row per permit per block; `FREQUENCY` = its locations on that block).
2. **Summary Statistics**: input `Stats_PermitPerBlock`; statistics `TrackingNumber` COUNT, `FREQUENCY` SUM, `MAX_ExpirationDate` MAX; case field `SUBBLOCKKEY` → `Stats_Permits`.
3. **Summary Statistics**: input `ServiceRequests_Block`; statistics `REQUESTID` COUNT, `INITIATEDDATE` MAX; case field `SUBBLOCKKEY` → `Stats_Requests`.

## 7. Enrich the road segments

1. **Join Field** (Data Management): `RoadwaySubblock` ← `Stats_Permits` on `SUBBLOCKKEY`, fields `COUNT_TrackingNumber`, `SUM_FREQUENCY`, `MAX_MAX_ExpirationDate`.
2. **Join Field**: `RoadwaySubblock` ← `Stats_Requests` on `SUBBLOCKKEY`, fields `COUNT_REQUESTID`, `MAX_INITIATEDDATE`.
3. **Alter Field** to readable names and aliases:

| Joined field | New name | Alias |
|---|---|---|
| `COUNT_TrackingNumber` | `PermitCount` | Permits on block |
| `SUM_FREQUENCY` | `PermitLocations` | Permit locations on block |
| `MAX_MAX_ExpirationDate` | `PermitMaxExpiration` | Latest permit expiration |
| `COUNT_REQUESTID` | `RequestCount` | Open service requests on block |
| `MAX_INITIATEDDATE` | `RequestMaxInitiated` | Latest service request created |

4. **Calculate Field**: `PermitCount`, `PermitLocations` and `RequestCount` = 0 where they are null (blocks with none).
5. **Add Field** `HasPermitAndRequest` (Text 3) + **Calculate Field**: `"Yes" if !PermitCount! > 0 and !RequestCount! > 0 else "No"`.

## 8. Map

Layers, top to bottom (no polished symbology needed):

- *Permits moved off an alley*: `Permits_Snapped_Block` with the definition query `WasOnAlley = 'Yes'`, bright colour
- `Permits_Snapped_Block`
- `Permit_SnapMoves` (if made)
- `ServiceRequests_Block`
- `RoadwaySubblock` (enriched), with a simple highlight for `HasPermitAndRequest = 'Yes'`
- The three REST feeds

## 9. Checks before packaging

- The counts in step 2 match the notebook.
- Sum of `RequestCount` over all blocks = number of requests (692), less any further than 70 m from a street.
- Number of blocks with `HasPermitAndRequest = 'Yes'` is noted in the write-up.
- Geoprocessing history: Catalog pane → Project → **Geoprocessing History** lists every tool above.

## 10. Package

Share → **Package Project** (include the geodatabase and history; REST layers stay as references), or zip the project folder. Save as `FirstName_MiddleInitial_LastName_GIS.ppkx` / `.zip`, together with the exploration notebook.
