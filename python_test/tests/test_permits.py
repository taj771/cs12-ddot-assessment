"""Tests for picking out the utility permits (step 3)."""

import pytest

from enrichment.step3_permits import find_utility


def permit(applicant="", permittee="", owner=""):
    # A permit row with just the three name columns
    return {"ApplicantCompany": applicant, "PermitteeName": permittee, "OwnerName": owner}


@pytest.mark.parametrize("name, utility", [
    ("DC Water", "DC Water"),
    ("DCWater/CIP", "DC Water"),
    ("District of Columbia Water and Sewer Authority", "DC Water"),
    ("Potomac Electric Power Company", "PEPCO"),
    ("Pepco Holdings Inc", "PEPCO"),
    ("Washington Gas Light Co", "Washington Gas"),
    ("Wash Gas & Light Co.", "Washington Gas"),
    ("WGL", "Washington Gas"),
])
def test_name_variants_are_recognised(name, utility):
    assert find_utility(permit(applicant=name)) == utility


def test_utility_found_in_permittee_or_owner():
    assert find_utility(permit(applicant="ABC Permits LLC", permittee="Pepco")) == "PEPCO"
    assert find_utility(permit(applicant="ABC Permits LLC", owner="DC WATER")) == "DC Water"


def test_other_companies_are_not_utilities():
    assert find_utility(permit(applicant="Clark Construction", permittee="Washington Hospital")) is None
