"""validate.py: required-field drops with reasons, and de-dupe by listing_url."""

from __future__ import annotations

from listing_extractor.mapping import Listing
from listing_extractor.validate import validate_rows


def _row(**kw) -> Listing:
    base = dict(
        listing_url="https://p.example/property-1",
        suburb="Riverbend",
        state="VIC",
        postcode="3999",
        price_text="$1,000,000",
        property_type="House",
    )
    base.update(kw)
    return Listing(**base)


def test_valid_row_passes():
    result = validate_rows([_row()])
    assert len(result.valid) == 1
    assert result.dropped == []


def test_missing_required_field_is_dropped_with_a_reason():
    result = validate_rows([_row(listing_url="")])
    assert result.valid == []
    assert len(result.dropped) == 1
    assert "missing required" in result.dropped[0].reason
    assert "listing_url" in result.dropped[0].reason


def test_regression_4_locality_only_row_still_validates():
    # address_full is not required; suburb/state/postcode are present.
    result = validate_rows([_row(address_full="")])
    assert len(result.valid) == 1


def test_range_price_row_validates_when_price_text_present():
    result = validate_rows([_row(price_text="$800,000 - $850,000", price_value=None)])
    assert len(result.valid) == 1


def test_duplicate_listing_url_counted_once():
    a = _row(listing_url="https://p.example/property-42")
    b = _row(listing_url="https://p.example/property-42", price_text="$999,000")
    result = validate_rows([a, b])
    assert len(result.valid) == 1
    assert len(result.dropped) == 1
    assert result.dropped[0].reason == "duplicate listing_url"


def test_reason_counts_group_drops():
    rows = [
        _row(),
        _row(state=""),
        _row(postcode=""),
        _row(listing_url="https://p.example/property-1"),  # dup of the first
    ]
    result = validate_rows(rows)
    counts = result.reason_counts()
    assert counts["duplicate listing_url"] == 1
    assert sum(v for k, v in counts.items() if k.startswith("missing required")) == 2


def test_fixture_pages_give_26_valid_2_dropped(all_search_listings):
    result = validate_rows(all_search_listings)
    assert result.seen == 28
    assert len(result.valid) == 26
    assert len(result.dropped) == 2
    reasons = result.reason_counts()
    assert reasons["duplicate listing_url"] == 1
    assert any(k.startswith("missing required") for k in reasons)
    # Every kept row has a unique URL.
    urls = [r.listing_url for r in result.valid]
    assert len(urls) == len(set(urls))
