"""shape.py: what counts as a listing, and project detection."""

from __future__ import annotations

from listing_extractor.blob import iter_listings
from listing_extractor.shape import listing_kind, looks_like_listing

from .conftest import by_id


def test_requires_address_suburb():
    # An id + shape marker but no suburb -> not a listing.
    assert not looks_like_listing(
        {"id": "1", "price": {"display": "$1"}, "address": {"state": "vic"}}
    )
    assert looks_like_listing(
        {
            "id": "1",
            "price": {"display": "$1"},
            "address": {"suburb": "Richmond", "state": "vic"},
        }
    )


def test_requires_an_id_and_a_shape_marker():
    addr = {"address": {"suburb": "Richmond"}}
    assert not looks_like_listing(addr)  # no id, no shape
    assert not looks_like_listing({**addr, "id": "1"})  # id but no shape
    assert not looks_like_listing({**addr, "price": {}})  # shape but no id
    assert looks_like_listing({**addr, "_links": {}, "generalFeatures": {}})


def test_regression_1_agency_card_is_not_a_listing(search_page_1):
    # The fixture's agency card has an address block and a logo image but no
    # address.suburb. It must not appear among the parsed rows.
    assert len(search_page_1) == 24  # 25 nodes on the page, 1 is the agency card
    for listing in search_page_1:
        assert "agency" not in listing.listing_url
        assert listing.suburb  # every real row has a suburb


def test_regression_1_agency_card_dropped_by_iter_listings():
    agency_card = {
        "id": "agency-xyz",
        "_links": {"canonical": {"href": "/agency/some-agency?cid={cid}"}},
        "address": {"display": {"fullAddress": "16C Darlot Street, HORSHAM"}},
        "media": {"images": [{"templatedUrl": "https://x/{size}/logo.jpg"}]},
    }
    assert list(iter_listings({"card": agency_card})) == []


def test_listing_kind_project_from_type_text():
    assert listing_kind({"propertyType": {"display": "New Apartments"}}) == "project"
    assert listing_kind({"propertyType": {"id": "project"}}) == "project"
    assert listing_kind({"propertyType": {"display": "House"}}) == "standard"


def test_regression_3_fixture_project_is_tagged(all_search_listings):
    project = by_id(all_search_listings, "780202")
    assert project.listing_kind == "project"
