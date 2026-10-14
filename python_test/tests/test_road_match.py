"""Tests for matching a location to a road (step 4).

The road lookup service is replaced by a fake that returns made-up segments,
so these tests don't need the internet.
"""

import pytest

from enrichment import step4_road_match
from enrichment.step4_road_match import nearest_road, street_in_address


def segment(key, name, road_type, distance):
    # One segment as the road lookup service returns it
    return {"subBlockKey": key, "routeName": name, "routeType": road_type, "offsetInMeters": distance}


@pytest.fixture
def roads_nearby(monkeypatch):
    # Replace the road lookup with a fake: give it what the 50 m and 100 m searches should find
    def use(within_50=(), within_100=()):
        def fake_segments_near(x, y, radius):
            found = list(within_50) if radius == 50 else list(within_100)
            return sorted(found, key=lambda c: c["offsetInMeters"])
        monkeypatch.setattr(step4_road_match, "segments_near", fake_segments_near)
    return use


@pytest.mark.parametrize("address, street", [
    ("1300 - 1399 BLOCK OF NAYLOR COURT NW", "NAYLOR CT NW"),
    ("3302 15TH STREET NW", "15TH ST NW"),
    ("2655 15TH STREET NW", "15TH ST NW"),
    ("3333 GEORGIA AVENUE NW", "GEORGIA AVE NW"),
])
def test_street_in_address(address, street):
    assert street_in_address(address) == street


def test_nearest_road_is_used(roads_nearby):
    roads_nearby(within_50=[segment("a", "18TH ST NW", "Street", 2), segment("b", "U ST NW", "Street", 20)])
    match = nearest_road(0, 0, "2000 18TH STREET NW")
    assert match["SubBlockKey"] == "a"
    assert match["MatchNote"] == "matched"


def test_alley_is_skipped(roads_nearby):
    roads_nearby(within_50=[segment("alley", "Alley-1", "Alley", 3), segment("a", "MORTON ST NW", "Street", 18)])
    match = nearest_road(0, 0, "3333 GEORGIA AVENUE NW")
    assert match["SubBlockKey"] == "a"
    assert match["MatchNote"] == "skipped a nearer alley"


def test_segment_within_1_m_is_kept_as_a_tie(roads_nearby):
    roads_nearby(within_50=[
        segment("s", "S ST NW", "Street", 0.0),
        segment("w", "WISCONSIN AVE NW", "Street", 0.4),
        segment("far", "R ST NW", "Street", 30),
    ])
    match = nearest_road(0, 0, "WISCONSIN AVENUE NW AND S STREET NW")
    assert match["SubBlockKey"] == "s"
    assert match["TiedSubBlockKeys"] == "w"


def test_wider_search_prefers_the_address_street(roads_nearby):
    roads_nearby(within_100=[segment("o", "O ST NW", "Street", 51), segment("c", "NAYLOR CT NW", "Street", 60)])
    match = nearest_road(0, 0, "1300 - 1399 BLOCK OF NAYLOR COURT NW")
    assert match["SubBlockKey"] == "c"
    assert match["MatchNote"].startswith("address street on wider search")


def test_wider_search_without_the_address_street_is_marked_check(roads_nearby):
    roads_nearby(within_100=[segment("o", "O ST NW", "Street", 51)])
    match = nearest_road(0, 0, "1300 - 1399 BLOCK OF NAYLOR COURT NW")
    assert match["SubBlockKey"] == "o"
    assert match["MatchNote"].endswith("- check")


def test_no_road_within_100_m_gives_a_blank(roads_nearby):
    roads_nearby(within_100=[segment("alley", "Alley-1", "Alley", 40)])
    match = nearest_road(0, 0, "1900 MASSACHUSETTS AVENUE SE")
    assert match["SubBlockKey"] is None
    assert match["MatchNote"] == "no road within 100 m"
