"""Generate the synthetic fixture pages under ``tests/fixtures/pages/``.

The pages are structurally faithful to the real portal blob -- the assignment
statement, multi-level stringified JSON, urql-style cache keys, templated image
URLs with ``{size}`` -- but every name, address and domain is synthetic
(``*.example`` domains, Faker names). Re-run after changing the blob shape:

    python scripts/generate_fixtures.py

Each element maps to one of the six live regressions from CLAUDE.md; see the
generated ``tests/fixtures/pages/README.md``.
"""

from __future__ import annotations

import json
from pathlib import Path

from faker import Faker

FIXTURE_DIR = Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "pages"
IMG_HOST = "https://i.example-portal.example"
APP_KEY = "resi-property_listing-experience-web"

fake = Faker("en_AU")
Faker.seed(20260830)

SUBURB = {"suburb": "Riverbend", "state": "vic", "postcode": "3999"}


def _img(hash_: str, n: int) -> dict:
    # Templated URL: the real portal ships a "{size}" segment the client must
    # expand. The fixture keeps the brace so regression 6 is exercised.
    return {"templatedUrl": f"{IMG_HOST}/{{size}}/{hash_}/image{n}.jpg"}


def _images(hash_: str, count: int) -> dict:
    return {"images": [_img(hash_, i) for i in range(1, count + 1)]}


def _canonical(kind: str, listing_id: str) -> dict:
    slug = f"property-{kind}-{SUBURB['state']}-{SUBURB['suburb'].lower()}-{listing_id}"
    return {"canonical": {"href": f"/{slug}"}}


def _address(street: str | None) -> dict:
    addr = dict(SUBURB)
    if street:
        full = f"{street}, {SUBURB['suburb'].upper()} {SUBURB['state'].upper()} {SUBURB['postcode']}"
        addr["display"] = {"fullAddress": full, "shortAddress": street}
    return addr


def _features(beds: int, baths: int, cars: int) -> dict:
    return {
        "bedrooms": {"value": beds},
        "bathrooms": {"value": baths},
        "parkingSpaces": {"value": cars},
    }


def standard_listing(
    listing_id: str,
    kind: str,
    display_type: str,
    street: str,
    beds: int,
    baths: int,
    cars: int,
    price_display: str,
    price_value: int | None,
    *,
    land: str | None = None,
    images: int = 3,
) -> dict:
    price: dict = {"display": price_display}
    if price_value is not None:
        price["value"] = price_value
    obj: dict = {
        "listingId": listing_id,
        "id": listing_id,
        "_links": _canonical(kind, listing_id),
        "address": _address(street),
        "propertyType": {"id": kind, "display": display_type},
        "generalFeatures": _features(beds, baths, cars),
        "price": price,
        "description": fake.paragraph(nb_sentences=3),
        "listingCompany": {"name": fake.company() + " Realty"},
        "listers": [{"name": fake.name()}, {"name": fake.name()}],
        "media": _images(fake.hexify("^^^^^^^^"), images),
        "dateListed": "2026-08-2" + listing_id[-1] + "T00:00:00Z",
    }
    if land:
        obj["propertySizes"] = {
            "land": {"displayValue": land, "sizeUnit": {"displayValue": "m²"}}
        }
    return obj


def agency_card(card_id: str) -> dict:
    # Regression 1: an agency office card. It has an "address" dict and a
    # media/logo, but no address.suburb -- must not be collected as a listing.
    return {
        "id": f"agency-{card_id}",
        "_links": {
            "canonical": {"href": f"/agency/{fake.slug()}-{card_id}?cid={{cid}}"}
        },
        "address": {
            "display": {
                "fullAddress": f"{fake.building_number()} {fake.street_name()}, RIVERBEND"
            }
        },
        "media": {"images": [_img("agencylogo", 1)]},
        "branding": {"name": fake.company() + " Realty"},
    }


def build_search_blob(listings: list[dict], max_page: int) -> str:
    """Wrap listings in the nested, multi-level-stringified cache shape."""
    inner_data = {
        "buySearch": {
            "results": {
                "exact": {"items": listings},
                "pagination": {"maxPageNumberAvailable": max_page},
            }
        }
    }
    urql_cache = {
        "buySearch({...})": {
            "data": json.dumps(inner_data),  # level 2 stringify
            "error": None,
        }
    }
    argonaut = {
        APP_KEY: {
            "urqlClientCache": json.dumps(urql_cache),  # level 1 stringify
        },
        "meta": {"channel": "buy", "suburb": SUBURB["suburb"]},
    }
    return json.dumps(argonaut)


def build_detail_blob(listing: dict) -> str:
    inner_data = {"listingByIdV2": listing}
    urql_cache = {
        "listingByIdV2({id})": {"data": json.dumps(inner_data), "error": None}
    }
    argonaut = {APP_KEY: {"urqlClientCache": json.dumps(urql_cache)}}
    return json.dumps(argonaut)


HTML = """<!doctype html>
<html lang="en-AU">
<head>
<meta charset="utf-8">
<title>{title}</title>
</head>
<body>
<div id="app"><!-- server-rendered listing cards omitted from the fixture --></div>
<script>
window.ArgonautExchange = {blob};
window.ArgonautExchange = undefined;  // the real page wipes the variable after hydration
</script>
</body>
</html>
"""


def _page(title: str, blob: str) -> str:
    return HTML.format(title=title, blob=blob)


def _standard_pool() -> list[dict]:
    """Eighteen ordinary listings with full, valid data."""
    specs = [
        ("house", "House", 3, 2, 2, "$1,250,000", 1_250_000, "540"),
        ("apartment", "Apartment", 2, 1, 1, "$625,000", 625_000, None),
        ("townhouse", "Townhouse", 3, 2, 1, "$890,000", 890_000, "210"),
        ("house", "House", 4, 2, 2, "$1.35m", None, "620"),
        ("apartment", "Apartment", 1, 1, 1, "$430,000", 430_000, None),
        ("house", "House", 5, 3, 4, "$2,100,000", 2_100_000, "1,012"),
        ("townhouse", "Townhouse", 2, 1, 1, "$560,000", 560_000, "150"),
        ("house", "House", 3, 1, 1, "$975,000", 975_000, "480"),
        ("apartment", "Apartment", 2, 2, 1, "$720,000", 720_000, None),
        ("house", "House", 4, 3, 2, "$1,680,000", 1_680_000, "700"),
        ("villa", "Villa", 3, 2, 2, "$845,000", 845_000, "300"),
        ("house", "House", 3, 2, 2, "$1,125,000", 1_125_000, "505"),
        ("apartment", "Apartment", 3, 2, 2, "$910,000", 910_000, None),
        ("house", "House", 2, 1, 1, "$680,000", 680_000, "395"),
        ("townhouse", "Townhouse", 3, 2, 2, "$935k", None, "205"),
        ("house", "House", 6, 4, 6, "$3,250,000", 3_250_000, "2,400"),
        ("apartment", "Apartment", 1, 1, 0, "$385,000", 385_000, None),
        ("house", "House", 4, 2, 2, "$1,420,000", 1_420_000, "660"),
    ]
    pool = []
    for i, (kind, disp, b, ba, c, pd, pv, land) in enumerate(specs, start=1):
        listing_id = f"7{i:05d}"
        pool.append(
            standard_listing(
                listing_id,
                kind,
                disp,
                fake.street_address().split("\n")[0],
                b,
                ba,
                c,
                pd,
                pv,
                land=land,
            )
        )
    return pool


def _regression_listings() -> list[dict]:
    out = []

    # Regression 2: no _links.canonical -> listing_url stays empty -> dropped.
    no_link = standard_listing(
        "780101",
        "house",
        "House",
        "9 Kestrel Court",
        3,
        2,
        2,
        "$1,050,000",
        1_050_000,
        land="510",
    )
    del no_link["_links"]
    out.append(no_link)

    # Regression 3: project / New Apartments -- range price per unit, no single
    # bed/bath count. Row stays valid; price_value and features are empty.
    project = {
        "listingId": "780202",
        "id": "780202",
        "_links": _canonical("project", "780202"),
        "address": _address("The Heights, 200 Skyline Road"),
        "propertyType": {"id": "project", "display": "New Apartments"},
        "price": {"display": "$450,000 - $780,000"},
        "description": fake.paragraph(nb_sentences=2),
        "listingCompany": {"name": fake.company() + " Projects"},
        "listers": [{"name": fake.name()}],
        "media": _images(fake.hexify("^^^^^^^^"), 4),
        "channel": "buy",
    }
    out.append(project)

    # Regression 4: rural/acreage listing with the street address withheld.
    # suburb/state/postcode are still present -> keep the row, address_full "".
    hidden = standard_listing(
        "780303",
        "acreage",
        "Acreage",
        "unused",
        4,
        2,
        6,
        "$1,900,000",
        1_900_000,
        land="21,000",
    )
    hidden["address"] = _address(None)  # no display block at all
    out.append(hidden)

    # Regression 5: price text variants.
    out.append(
        standard_listing(
            "780404",
            "house",
            "House",
            "3 Wattle Lane",
            3,
            1,
            2,
            "Contact Agent",
            None,
            land="430",
        )
    )
    out.append(
        standard_listing(
            "780505",
            "house",
            "House",
            "17 Rosella Street",
            4,
            2,
            2,
            "$800,000 - $850,000",
            None,
            land="600",
        )
    )
    out.append(
        standard_listing(
            "780606",
            "house",
            "House",
            "42 Boronia Avenue",
            5,
            3,
            3,
            "Offers over $1,200,000",
            None,
            land="900",
        )
    )

    return out


def generate() -> list[Path]:
    FIXTURE_DIR.mkdir(parents=True, exist_ok=True)

    pool = _standard_pool()
    regressions = _regression_listings()

    # --- Search page 1: 18 standard + 6 regression + 1 agency card = 25 nodes,
    #     24 of them listing-shaped. ---
    page1 = pool[:18] + regressions
    page1_nodes = page1[:12] + [agency_card("AB12")] + page1[12:]
    p1 = FIXTURE_DIR / "search-buy-riverbend-1.html"
    p1.write_text(
        _page("Riverbend buy listings - page 1", build_search_blob(page1_nodes, 3)),
        encoding="utf-8",
    )

    # --- Search page 2: repeats page 1's first listing (dedupe target) plus
    #     three listings not seen on page 1. ---
    page2 = [pool[0]] + _extra_page2_listings()
    p2 = FIXTURE_DIR / "search-buy-riverbend-2.html"
    p2.write_text(
        _page("Riverbend buy listings - page 2", build_search_blob(page2, 3)),
        encoding="utf-8",
    )

    # --- Detail page: a single listing at a different cache path, richer body. ---
    detail = standard_listing(
        "790909",
        "house",
        "House",
        "5 Heron Close",
        4,
        2,
        2,
        "$1,540,000",
        1_540_000,
        land="655",
        images=8,
    )
    detail["description"] = fake.paragraph(nb_sentences=8)
    p3 = FIXTURE_DIR / "detail-buy-riverbend-house.html"
    p3.write_text(
        _page("5 Heron Close, Riverbend", build_detail_blob(detail)), encoding="utf-8"
    )

    _write_readme()
    return [p1, p2, p3]


def _extra_page2_listings() -> list[dict]:
    specs = [
        ("house", "House", 3, 2, 2, "$1,190,000", 1_190_000, "515"),
        ("apartment", "Apartment", 2, 1, 1, "$505,000", 505_000, None),
        ("townhouse", "Townhouse", 4, 3, 2, "$1,050,000", 1_050_000, "260"),
    ]
    out = []
    for i, (kind, disp, b, ba, c, pd, pv, land) in enumerate(specs, start=1):
        out.append(
            standard_listing(
                f"8{i:05d}",
                kind,
                disp,
                fake.street_address().split("\n")[0],
                b,
                ba,
                c,
                pd,
                pv,
                land=land,
            )
        )
    return out


def _write_readme() -> None:
    (FIXTURE_DIR / "README.md").write_text(README, encoding="utf-8")


README = """# Fixture pages

**Synthetic.** These pages are generated by `scripts/generate_fixtures.py`. No
real listing, address, agent or agency appears here: names come from Faker, every
domain is a `*.example` domain, the suburb "Riverbend VIC 3999" is invented.

They are structurally faithful to the real portal: a `window.ArgonautExchange =
{...}` assignment inside a `<script>`, values stringified two levels deep in a
urql-style GraphQL cache, `maxPageNumberAvailable` nested in `pagination`,
templated image URLs carrying a `{size}` token, and the variable wiped right
after assignment (so a reader must take the script text, not the variable).

## What each element reproduces

| Element on the page | Live regression it reproduces |
|---|---|
| `agency-AB12` card (has `address` but no `address.suburb`, has a logo image) | 1 -- agency cards leaked in because the shape test accepted `address` + `media`. It must be dropped: require `address.suburb`, ignore `media`. |
| listing `780101` (no `_links`) | 2 -- a listing with no canonical link gets an empty `listing_url` and is dropped by validation, never a fabricated dead URL. |
| listing `780202` (`New Apartments`, price `$450,000 - $780,000`, no `generalFeatures`) | 3 -- project listings price per unit as a range and carry no single bed/bath. Map what exists, leave the rest empty, `listing_kind = project`. |
| listing `780303` (`address` has suburb/state/postcode but no `display`) | 4 -- rural/acreage listings hide the street address on purpose; keep the row with `address_full` empty. |
| listings `780404` / `780505` / `780606` (`Contact Agent`, `$800,000 - $850,000`, `Offers over $1,200,000`), plus `$1.35m` and `$935k` in the standard pool | 5 -- price text variants; a range leaves `price_value` empty but keeps `price_text`; `k`/`m` suffixes expand. |
| every `media.images[].templatedUrl` contains `{size}` | 6 -- templated image URLs must be expanded to a fixed size; never ship a `{...}`. |
| `search-buy-riverbend-2.html` repeats listing `700001` from page 1 | dedupe -- the same listing on two pages is counted once by `validate`. |
| `maxPageNumberAvailable: 3` nested in `results.pagination` | `find_max_page` locating the value several levels deep in stringified JSON. |

## Files

- `search-buy-riverbend-1.html` -- 24 listing-shaped nodes + 1 agency card.
- `search-buy-riverbend-2.html` -- 4 listings, one shared with page 1.
- `detail-buy-riverbend-house.html` -- one listing at a single-object cache path.
"""


if __name__ == "__main__":
    paths = generate()
    for p in paths:
        print("wrote", p)
