"""Helpers for downloading data from DC's public ArcGIS map services."""

import time

import pandas as pd
import requests

PAGE_SIZE = 2000  # max rows the DC services return per request
TIMEZONE = "America/New_York"

# One shared connection, reused across requests (much faster for thousands of calls)
session = requests.Session()


def get_json(url, params, attempts=4):
    """Request a URL and return the JSON reply, retrying if the connection fails."""
    for attempt in range(attempts):
        try:
            response = session.get(url, params=params, timeout=60)
            response.raise_for_status()
            data = response.json()
            break
        except (requests.RequestException, ValueError):
            if attempt == attempts - 1:
                raise
            time.sleep(2 ** attempt)  # wait 1, 2, 4 seconds

    # A bad query still comes back as HTTP 200, with the error inside the JSON
    if "error" in data:
        raise RuntimeError(f"Query failed for {url}: {data['error']}")
    return data


def fetch_layer(layer_url, where="1=1", fields="*", geometry=True):
    """Download all rows matching `where` and return them as a DataFrame.

    Dates are converted to DC local time, and coded columns get an extra
    `<column>_label` column with the readable value (e.g. ROADTYPE 4 -> "Alley").
    """
    params = {
        "where": where,
        "outFields": fields,
        "returnGeometry": str(geometry).lower(),
        "orderByFields": "OBJECTID",  # fixed order so pages don't overlap
        "resultRecordCount": PAGE_SIZE,
        "f": "json",
    }

    rows, offset = [], 0
    while True:
        data = get_json(f"{layer_url}/query", {**params, "resultOffset": offset})
        for feature in data["features"]:
            row = feature["attributes"]
            point = feature.get("geometry") or {}
            if "x" in point:
                row["x"], row["y"] = point["x"], point["y"]
            rows.append(row)
        if not data.get("exceededTransferLimit"):
            break
        offset += len(data["features"])

    table = pd.DataFrame(rows)

    # The layer description tells us which columns are dates and which are codes
    for field in get_json(layer_url, {"f": "json"})["fields"]:
        name = field["name"]
        if name not in table:
            continue
        if field["type"] == "esriFieldTypeDate":
            table[name] = pd.to_datetime(table[name], unit="ms", utc=True).dt.tz_convert(TIMEZONE)
        domain = field.get("domain") or {}
        if domain.get("type") == "codedValue":
            labels = {str(c["code"]): c["name"] for c in domain["codedValues"]}
            # Number columns with blanks come back as 7.0, so drop the ".0" before matching
            codes = table[name].astype("string").str.removesuffix(".0")
            table[name + "_label"] = codes.map(labels)

    return table
