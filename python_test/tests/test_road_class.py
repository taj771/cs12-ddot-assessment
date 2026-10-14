"""Tests for the functional class of each location and of each permit (step 5).

The Roadway SubBlock layer is replaced by a small made-up table.
"""

import pandas as pd

from enrichment import step5_road_class
from enrichment.step5_road_class import add_road_class

SEGMENTS = pd.DataFrame({
    "SubBlockKey": ["w", "s", "k1", "k2"],
    "RoadName": ["WISCONSIN AVE NW", "S ST NW", "KALORAMA RD NW", "18TH ST NW"],
    "FHWAClassCode": pd.array([3, 7, 7, 4], dtype="Int64"),
    "FHWAClass": ["Principal Arterial - Other", "Local", "Local", "Minor Arterial"],
    "SegmentRoadType": ["Street"] * 4,
})


def run(permits, monkeypatch):
    # Add the classes, looking segments up in the made-up table instead of the map service
    monkeypatch.setattr(step5_road_class, "segment_classes",
                        lambda keys: SEGMENTS[SEGMENTS["SubBlockKey"].isin(keys)])
    return add_road_class(pd.DataFrame(permits))


def location(permit, key, tied="", note="matched"):
    # One permit location as it comes out of step 4
    return {"TrackingNumber": permit, "SubBlockKey": key, "RoadName": None, "MatchNote": note, "TiedSubBlockKeys": tied}


def test_highest_class_is_the_smallest_code_across_the_permit(monkeypatch):
    result = run([location(1, "k1"), location(1, "k2"), location(2, "k1")], monkeypatch)
    assert result["FHWAClass"].tolist() == ["Local", "Minor Arterial", "Local"]
    assert result["HighestFHWAClass"].tolist() == ["Minor Arterial", "Minor Arterial", "Local"]


def test_corner_takes_the_higher_class_and_records_the_cross_road(monkeypatch):
    # Step 4 chose S St (Local), with Wisconsin Ave (Principal Arterial) tied at the same spot
    result = run([location(1, "s", tied="w")], monkeypatch).iloc[0]
    assert result["RoadName"] == "WISCONSIN AVE NW"
    assert result["FHWAClass"] == "Principal Arterial - Other"
    assert bool(result["AtIntersection"])
    assert result["CrossRoadName"] == "S ST NW"
    assert result["MatchNote"].endswith("tie at intersection - higher class used")


def test_location_without_a_road_stays_blank(monkeypatch):
    result = run([location(1, None, note="no road within 100 m"), location(1, "k2")], monkeypatch)
    assert pd.isna(result["FHWAClassCode"].iloc[0])
    assert result["HighestFHWAClass"].tolist() == ["Minor Arterial", "Minor Arterial"]
