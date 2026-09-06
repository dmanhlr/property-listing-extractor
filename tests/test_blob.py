"""blob.py: finding the assignment, scanning one balanced object, un-stringifying."""

from __future__ import annotations

import json

from listing_extractor.blob import extract_blob, find_max_page, iter_listings

APP_KEY = "resi-property_listing-experience-web"


def _listing(listing_id: str = "1") -> dict:
    return {
        "listingId": listing_id,
        "_links": {"canonical": {"href": f"/property-house-vic-x-{listing_id}"}},
        "address": {"suburb": "X", "state": "vic", "postcode": "3000"},
        "propertyType": {"display": "House"},
        "price": {"display": "$1", "value": 1},
    }


def test_empty_html_yields_empty_list():
    assert extract_blob("") == {}
    assert extract_blob("<html><body>no script here</body></html>") == {}
    assert list(iter_listings(extract_blob("<html></html>"))) == []


def test_reads_script_text_not_the_wiped_variable():
    # The real page assigns the blob then sets the variable to undefined. A
    # reader must take the script text, which still holds the data.
    blob = {
        APP_KEY: {
            "urqlClientCache": json.dumps(
                {
                    "q": {
                        "data": json.dumps(
                            {"search": {"results": {"exact": {"items": [_listing()]}}}}
                        )
                    }
                }
            )
        }
    }
    html = (
        "<script>window.ArgonautExchange = "
        + json.dumps(blob)
        + ";\nwindow.ArgonautExchange = undefined;</script>"
    )
    got = extract_blob(html)
    assert got != {}
    assert len(list(iter_listings(got))) == 1


def test_braces_inside_strings_do_not_end_the_scan():
    blob = {"note": "a } and a ] and a { inside text", "n": 1}
    html = "<script>window.ArgonautExchange = " + json.dumps(blob) + ";</script>"
    assert extract_blob(html) == blob


def test_json_stringified_three_levels_deep():
    listing = _listing("deep")
    level3 = json.dumps({"search": {"results": {"exact": {"items": [listing]}}}})
    level2 = json.dumps({"query-hash": {"data": level3}})
    level1 = json.dumps({"urqlClientCache": level2})
    blob = {APP_KEY: level1}
    html = "<script>window.ArgonautExchange = " + json.dumps(blob) + ";</script>"
    listings = list(iter_listings(extract_blob(html)))
    assert len(listings) == 1
    assert listings[0]["listingId"] == "deep"


def test_find_max_page_at_depth():
    level3 = json.dumps(
        {"search": {"results": {"pagination": {"maxPageNumberAvailable": 9}}}}
    )
    level2 = json.dumps({"q": {"data": level3}})
    blob = {APP_KEY: {"urqlClientCache": level2}}
    html = "<script>window.ArgonautExchange = " + json.dumps(blob) + ";</script>"
    assert find_max_page(extract_blob(html)) == 9


def test_find_max_page_absent_returns_none():
    blob = {APP_KEY: {"urqlClientCache": json.dumps({"q": {"data": "{}"}})}}
    assert find_max_page(blob) is None


def test_second_script_carries_the_blob():
    other = "<script>var x = {a:1};</script>"
    blob = {"k": 1}
    good = "<script>window.ArgonautExchange = " + json.dumps(blob) + ";</script>"
    assert extract_blob("<html>" + other + good + "</html>") == blob
