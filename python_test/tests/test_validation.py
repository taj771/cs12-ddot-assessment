"""Tests for the check against MAR addresses (step 6)."""

import pandas as pd

from enrichment.step6_validation import review_reason


def row(**values):
    # A location where step 5 matched Morton St (Local); change any value per test
    base = {
        "WorkLocationFullAddress": "3333 GEORGIA AVENUE NW",
        "RoadName": "MORTON ST NW", "FHWAClassCode": 7, "CrossRoadName": None,
        "MARRoadName": "GEORGIA AVE NW", "MARClassCode": 3, "MARClass": "Principal Arterial - Other",
    }
    return pd.Series({**base, **values})


def test_flagged_when_mar_and_address_both_name_another_road():
    assert review_reason(row()) == "MAR and address say GEORGIA AVE NW (Principal Arterial - Other)"


def test_not_flagged_when_the_address_agrees_with_our_road():
    # MAR picked a corner house on the cross street
    assert review_reason(row(WorkLocationFullAddress="3300 - 3399 BLOCK OF MORTON STREET NW")) == ""


def test_not_flagged_when_the_class_is_the_same():
    assert review_reason(row(MARClassCode=7)) == ""


def test_not_flagged_when_mar_names_the_cross_road_at_a_corner():
    assert review_reason(row(CrossRoadName="GEORGIA AVE NW")) == ""


def test_not_flagged_without_a_mar_address():
    assert review_reason(row(MARRoadName=None, MARClassCode=pd.NA)) == ""
