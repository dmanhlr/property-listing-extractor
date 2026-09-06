"""mapping.py: price parsing, image expansion, the field map, the regressions."""

from __future__ import annotations

from listing_extractor.mapping import (
    expand_image_url,
    map_listing,
    parse_price_value,
)

from .conftest import by_id

# --- price text variants (regression 5) ---------------------------------------


def test_parse_price_plain():
    assert parse_price_value("$1,250,000") == 1_250_000


def test_parse_price_k_and_m_suffixes():
    assert parse_price_value("$1.25m") == 1_250_000
    assert parse_price_value("$935k") == 935_000
    assert parse_price_value("$900K") == 900_000


def test_parse_price_offers_over_keeps_the_single_figure():
    assert parse_price_value("Offers over $1,200,000") == 1_200_000


def test_parse_price_range_returns_none():
    assert parse_price_value("$800,000 - $850,000") is None
    assert parse_price_value("From $500,000 to $600,000") is None
    assert parse_price_value("$450,000 – $780,000") is None  # en-dash


def test_parse_price_contact_agent_returns_none():
    assert parse_price_value("Contact Agent") is None
    assert parse_price_value("") is None


def test_range_row_keeps_price_text_but_not_value():
    raw = {
        "id": "1",
        "_links": {"canonical": {"href": "/property-house-vic-x-1"}},
        "address": {"suburb": "X", "state": "vic", "postcode": "3000"},
        "propertyType": {"display": "House"},
        "price": {"display": "$800,000 - $850,000"},
    }
    row = map_listing(raw)
    assert row.price_text == "$800,000 - $850,000"
    assert row.price_value is None


# --- templated images (regression 6) ----------------------------------------


def test_expand_image_removes_every_template_token():
    url = "https://i.example/{size}/hash/{variant}/img.jpg"
    out = expand_image_url(url)
    assert "{" not in out and "}" not in out
    assert (
        out
        == "https://i.example/1144x858-format=webp/hash/1144x858-format=webp/img.jpg"
    )


def test_fixture_images_carry_no_braces(search_page_1):
    seen_any = False
    for listing in search_page_1:
        for url in listing.image_urls:
            seen_any = True
            assert "{" not in url and "}" not in url
    assert seen_any


# --- the field map ---------------------------------------------------------


def test_maps_core_fields(search_page_1):
    row = by_id(search_page_1, "700001")
    assert row.listing_url.endswith("700001")
    assert row.suburb == "Riverbend"
    assert row.state == "VIC"  # upper-cased from "vic"
    assert row.postcode == "3999"
    assert row.property_type == "House"
    assert row.bedrooms == 3 and row.bathrooms == 2 and row.car_spaces == 2
    assert row.land_size == "540 m²"
    assert "; " in row.agent_name  # two listers joined
    assert row.agency_name.endswith("Realty")


# --- regression 2: no canonical link --------------------------------------


def test_regression_2_missing_canonical_leaves_url_empty(all_search_listings):
    no_link = next(
        x for x in all_search_listings if x.address_full.startswith("9 Kestrel")
    )
    assert no_link.listing_url == ""


def test_regression_2_never_fabricates_from_id():
    raw = {
        "id": "150101076",
        "address": {"suburb": "X", "state": "vic", "postcode": "3000"},
        "propertyType": {"display": "House"},
        "price": {"display": "$1", "value": 1},
    }
    assert map_listing(raw).listing_url == ""


def test_regression_2_rejects_templated_canonical():
    raw = {
        "id": "1",
        "_links": {"canonical": {"href": "/agency/x?cid={cid}"}},
        "address": {"suburb": "X", "state": "vic", "postcode": "3000"},
        "propertyType": {"display": "House"},
        "price": {"display": "$1"},
    }
    assert map_listing(raw).listing_url == ""


# --- canonical link: relative kept offline, absolutised with a base ----------


def _rel_canonical_raw() -> dict:
    return {
        "id": "9",
        "_links": {"canonical": {"href": "/property-house-vic-x-9"}},
        "address": {"suburb": "X", "state": "vic", "postcode": "3000"},
        "propertyType": {"display": "House"},
        "price": {"display": "$1", "value": 1},
    }


def test_relative_canonical_kept_when_no_base_url():
    assert map_listing(_rel_canonical_raw()).listing_url == "/property-house-vic-x-9"


def test_relative_canonical_absolutised_against_base_url():
    row = map_listing(_rel_canonical_raw(), base_url="https://portal.example/")
    assert row.listing_url == "https://portal.example/property-house-vic-x-9"


def test_absolute_canonical_left_untouched_even_with_base_url():
    raw = _rel_canonical_raw()
    raw["_links"]["canonical"]["href"] = "https://other.example/listing/9"
    row = map_listing(raw, base_url="https://portal.example")
    assert row.listing_url == "https://other.example/listing/9"


# --- regression 3: project listing --------------------------------------


def test_regression_3_project_maps_what_exists_only(all_search_listings):
    project = by_id(all_search_listings, "780202")
    assert project.listing_kind == "project"
    assert project.property_type == "New Apartments"
    assert project.price_text == "$450,000 - $780,000"
    assert project.price_value is None
    assert (
        project.bedrooms == "" and project.bathrooms == "" and project.car_spaces == ""
    )


# --- regression 4: hidden street address --------------------------------


def test_regression_4_hidden_address_keeps_locality(all_search_listings):
    hidden = by_id(all_search_listings, "780303")
    assert hidden.address_full == ""
    assert hidden.suburb == "Riverbend"
    assert hidden.state == "VIC"
    assert hidden.postcode == "3999"
