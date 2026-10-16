# CS12 Data Scientist assessment (DDOT)

[![Python test](https://github.com/taj771/cs12-ddot-assessment/actions/workflows/python-test.yml/badge.svg)](https://github.com/taj771/cs12-ddot-assessment/actions/workflows/python-test.yml)

Tharaka A. Jayalath. My work on the three tests, all built on DC's public map services (data pulled 14-15 October 2026). Each folder has its own README with the approach, decisions and limitations.

| Test | Question | Result | Folder |
|---|---|---|---|
| **Python** | Which FHWA functional class of road is each 2026 utility occupancy permit on? | 4,983 permit locations (3,129 applications) matched to a road and class; corner locations take the higher class; 35 flagged for review against DC's address repository | [`python_test/`](python_test/) |
| **GIS** | Which road blocks have both excavation/paving permits and open service requests? | 4,147 blocks with permits, 673 with open requests, **199 with both**; permits on alleys snapped back to the street | [`gis_test/`](gis_test/) |
| **Tableau** | How long does DDOT take to approve new construction permits issued in FY26? | **8.7 business days** on average (median 2); resubmitted, multi-location, paving and overhead permits take 3 to 5 times longer | [`tableau_test/`](tableau_test/) |

## How the work is organised

Each test starts with a notebook that explores the data, because none of the layers has a data dictionary. The rules found there are then applied in scripts (Python, Tableau) or in ArcGIS Pro (GIS), and the results are checked against an independent calculation.

```
python_test/    enrichment/step1 ... step7   numbered in the order I worked: explore → download → filter → match → classify → check → output
                tests/                       unit tests for the matching rules (run on Windows and Linux by GitHub Actions)
gis_test/       notebooks/                   exploration of the three layers
                CS12_GIS/                    ArcGIS Pro project and geodatabase (the .ppkx package is in the submission zip)
tableau_test/   notebooks/                   exploration of the permit layers
                scripts/prepare_data.py      builds the data the workbook reads (business days, categories)
                DDOT_FY26_Permit_Approvals.twb
```

One finding affects all three tests: DDOT's permit status layers remove permits once they expire. The Tableau test measures this against DC's yearly permit layers and limits the approval times to the months that are complete; the Python and GIS READMEs explain what it means for their counts.

## Running it

Python 3.11. Each of `python_test/` and `tableau_test/` has its own `requirements.txt` and run instructions in its README. The Python unit tests run offline:

```
cd python_test
pip install -r requirements-dev.txt
python -m pytest
```
