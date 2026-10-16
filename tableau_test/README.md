# FY26 construction permit approval times

Tableau dashboard showing how long DDOT takes to approve new construction permits issued in FY26 (1 October 2025 - 30 September 2026), overall and by type of permit. Data pulled 15 October 2026.

Code and full history: https://github.com/taj771/cs12-ddot-assessment (this test: [`tableau_test/`](https://github.com/taj771/cs12-ddot-assessment/tree/main/tableau_test)).

**Result**

| | |
|---|---|
| **Average time to approve** | **8.7 business days** |
| Median | 2 business days |
| Permits | 1,227 new permits issued in FY26, applied for July - September 2026 |

Most permits are routine gas, water and sewer excavations that are approved within a day or two. Applications that DDOT sends back for changes, permits covering many locations, and paving, overhead or electric work take 3 to 5 times longer.

## What's in the folder

| File | Contents |
|---|---|
| `DDOT_FY26_Permit_Approvals.twbx` | **The workbook**, with the data inside. Opens in Tableau Desktop or Reader 2024.2 or later. |
| `DDOT_FY26_Permit_Approvals.twb` | The same workbook without the data (kept for version control) |
| `prepared_data/` | The four CSV files the workbook reads |
| `scripts/prepare_data.py` | Downloads the permits and builds the CSV files |
| `notebooks/step1_explore_permits.ipynb` | The data exploration the rules come from |

The dashboard **FY26 permit approvals** is one page, read from top to bottom: the answer, what makes approvals slower, and notes on the data.

| Sheet | Shows |
|---|---|
| Overall | Average and median business days to approve, and the number of permits |
| By work type | Excavation, paving, fixture, overhead work, several types, other |
| Excavation by utility | The excavation permits split by gas, water, sewer, electric, telecom, test pits |
| Resubmission | Whether DDOT asked the applicant to resubmit |
| By number of locations | How many locations the permit covers |
| By applicant | Washington Gas, DC Water, PEPCO, telecom companies, DC government, private |
| Data completeness | Permits per month in the yearly layers vs still in the permit layer |
| Full year: days to issue | Application to issue for every FY26 permit, by month |

Each bar shows the number of permits it is based on. Some groups are small (6 "Other" permits), so their averages are less reliable.

## Rebuilding the data

Needs Python 3.11 and an internet connection (DC's public map services, no key needed). In this folder:

```
python -m venv .venv
.venv\Scripts\activate            (macOS / Linux: source .venv/bin/activate)
pip install -r requirements.txt
python scripts/prepare_data.py
```

It takes about a minute and rewrites the files in `prepared_data/`. Then open the workbook and refresh the data sources. The numbers will change slightly on a later date, because the permit layer changes every night.

| CSV | One row per | Used by |
|---|---|---|
| `fy26_approvals.csv` | New permit applied for in FY26 and approved by 30 September 2026 (3,438) | All "days to approve" sheets |
| `fy26_days_to_issue.csv` | New permit applied for and issued in FY26, from the yearly layers (7,392) | Full year: days to issue |
| `fy26_completeness.csv` | Application month (12) | Data completeness |
| `dc_holidays.csv` | DC public holiday in FY26 (13) | Reference: the days that were skipped |

All dates are DC local time.

## How "days to approve" is measured

- **Permits**: new construction permits (`Renewal = 1`) applied for on or after 1 October 2025 and issued in FY26, from DDOT's construction permit layer (DDOT_TOPS layer 23). One row per permit (`TrackingNumber`); the layer has one row per work location.
- **Approval date**: `LastApprovalDate`, the date of the final review approval. The issue date is later: a permit is issued when the fee is paid (within an hour of payment for 97.5% of permits), and the wait for payment is up to the applicant, not DDOT.
- **Start date**: `ApplicationDate`, as the brief asks. DDOT's own `DaysToApprove` field starts when the application is ready for review. That is the same day for almost all permits (0.1 business days later on average), but some incomplete applications wait weeks.
- **Business days**: weekdays from the application day to the approval day, not counting DC public holidays. Approved on the same day = 0, the next working day = 1. The holidays come from the `holidays` Python package (US federal holidays plus DC Emancipation Day, moved to the observed weekday) and match DC's official list for 2026.

## Key decisions

| Question | Decision | Evidence |
|---|---|---|
| Which months to average over? | **Applications from July - September 2026** | The permit layer removes permits after they expire. Compared with DC's yearly permit layers, which keep every permit, it still holds 95-100% of July - September applications but only 3-64% of earlier months (3% for January). The permits that remain from early months are mostly long-running ones, which are also slower, so including them would make the average too high. |
| Why not use the yearly layers for approval times? | They have no approval date | They do have application and issue dates for every permit, so the full year is shown as **days to issue** instead, clearly labelled. |
| Which permits are new? | `Renewal = 1` in layer 23; in the yearly layers, permit numbers without a "-R1", "-R2"... ending | The yearly layers have no renewal field. The permit number rule agrees with layer 23 for every FY26 permit in both (3,080 new, 3,837 renewals, no differences). |
| Which permit categories? | Work type from the `IsExcavation`, `IsPaving`, `IsFixture`, `IsOverHeadWork` flags; excavation split by the utility named in the work items | The brief leaves the categories open. The flags are filled for every permit. Excavation is 89% of permits, so it is split further. |
| Third split | Resubmission requested | The clearest difference (23.5 vs 6.2 days), and something DDOT and applicants can act on. Applicant and number of locations are added as extra sheets. |
| Time zone | All dates in DC local time | Layer 23 sends UTC. The yearly layers send DC local time labelled as UTC (they are 4 or 5 hours off from layer 23 for the same permits), so they are read as local time. |

## Things to know when reading the results

- **The average is for permits applied for in July - September 2026.** It is the only part of FY26 where the permit layer is complete. The full-year chart (days to issue) covers every month.
- **Fast permits are slightly favoured.** Permits applied for in September only count if they were issued by 30 September. If every July - September permit approved by 30 September is included, issued or not, the average is 10.3 business days (1,536 permits).
- **The full-year chart falls toward September for the same reason.** An October 2025 application had a whole year to be issued and counted; a September 2026 one only a few weeks. It is not a trend.
- **Days to issue includes the wait for the applicant to pay** (about 4 business days on average after approval in July - September).
- **The holiday list doesn't include days the Mayor adds at short notice.**

## With more time

- Pull layer 23 regularly (e.g. weekly) and keep the copies, so approval times can be measured for the whole year.
- Ask DDOT whether the approval date can be added to the yearly layers.
- Show the time from application to "ready for review" separately: it is short for most permits but weeks for some incomplete applications.
