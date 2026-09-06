"""Turn a raw listing dict into a ``Listing`` row.

Rules carried from live data:
  * No canonical link -> ``listing_url`` stays empty (regression 2). A fabricated
    ``/{id}`` URL was dead; leave it blank and let validation drop the row.
  * Price text has many shapes: ``Contact agent``, ``Offers over $900k``,
    ``$1,250,000``, ``$800,000 - $850,000``. A range leaves ``price_value``
    empty but keeps ``price_text`` (regression 5).
  * Project listings map what exists and leave the rest empty (regression 3).
  * Rural/acreage listings hide the street address; suburb/state/postcode are
    still there, so keep the row with ``address_full`` empty (regression 4).
  * Templated image URLs contain ``{size}`` (or ``{...}``); expand to a fixed
    size and never ship a brace (regression 6).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from listing_extractor.shape import listing_kind

# "$" then a number with optional thousands separators and optional k/m suffix.
_PRICE_TOKEN = re.compile(r"\$\s?(\d{1,3}(?:[,\s]?\d{3})*(?:\.\d+)?)\s*([mMkK])?")
# Any hint that the price is a span rather than a single figure.
_RANGE_HINT = re.compile(r"\bto\b|\bfrom\b|[-–—]", re.IGNORECASE)
# A templated segment in an image URL, e.g. "{size}" or "{cid}".
_TEMPLATE_TOKEN = re.compile(r"\{[^}]+\}")
_IMAGE_SIZE = "1144x858-format=webp"


@dataclass
class Listing:
    """One output row. Field order matches ``listing_extractor.FIELDNAMES``."""

    listing_url: str = ""
    address_full: str = ""
    suburb: str = ""
    state: str = ""
    postcode: str = ""
    price_text: str = ""
    price_value: float | None = None
    property_type: str = ""
    bedrooms: int | str = ""
    bathrooms: int | str = ""
    car_spaces: int | str = ""
    land_size: str = ""
    description: str = ""
    agent_name: str = ""
    agency_name: str = ""
    listing_date: str = ""
    image_urls: list[str] = field(default_factory=list)
    # Not exported; used by the CLI summary and tests. "standard" | "project".
    listing_kind: str = "standard"

    def as_row(self) -> dict[str, Any]:
        """Dict of just the exported fields, in schema order."""
        from listing_extractor.schema import FIELDNAMES

        return {name: getattr(self, name) for name in FIELDNAMES}


def _g(d: Any, *path: str, default: Any = None) -> Any:
    cur = d
    for p in path:
        if not isinstance(cur, dict):
            return default
        cur = cur.get(p)
        if cur is None:
            return default
    return cur


def _feature(raw: dict, name: str) -> int | str:
    """A general feature value (bedrooms/bathrooms/parkingSpaces).

    Tries ``generalFeatures.<name>.value``, then ``generalFeatures.<name>``, then
    a top-level key. Returns "" when the source does not expose it -- never a
    guessed 0 (regression 3: project listings have no single count).
    """
    v = _g(raw, "generalFeatures", name, "value")
    if v is None:
        v = _g(raw, "generalFeatures", name)
    if v is None:
        v = raw.get(name)
    if isinstance(v, dict):
        v = v.get("value")
    if isinstance(v, bool):  # guard: bool is an int subclass
        return ""
    return v if isinstance(v, int) else (v or "")


def parse_price_value(text: str) -> float | None:
    """A single dollar figure from ``text``, or ``None``.

    Returns ``None`` for range text (``$800k - $850k``, ``from ... to ...``) and
    for text with no or several dollar tokens (``Contact agent``). Applies
    ``k`` / ``m`` suffixes.
    """
    if not text:
        return None
    if _RANGE_HINT.search(text):
        return None
    matches = _PRICE_TOKEN.findall(text)
    if len(matches) != 1:
        return None
    num, suffix = matches[0]
    try:
        val = float(num.replace(",", "").replace(" ", ""))
    except ValueError:
        return None
    if suffix.lower() == "m":
        val *= 1_000_000
    elif suffix.lower() == "k":
        val *= 1_000
    return val if val > 0 else None


def expand_image_url(url: str) -> str:
    """Replace every ``{...}`` template token with a fixed size."""
    return _TEMPLATE_TOKEN.sub(_IMAGE_SIZE, url)


def _images(raw: dict) -> list[str]:
    imgs = _g(raw, "media", "images", default=None) or raw.get("images") or []
    out: list[str] = []
    for im in imgs:
        if isinstance(im, str):
            url = im
        elif isinstance(im, dict):
            url = im.get("templatedUrl") or im.get("url") or im.get("href") or ""
        else:
            url = ""
        if url:
            out.append(expand_image_url(url))
    return out


def _agents(raw: dict) -> str:
    listers = raw.get("listers") or _g(raw, "advertising", "listers") or []
    names = [
        (lister.get("name") or "").strip()
        for lister in listers
        if isinstance(lister, dict)
    ]
    return "; ".join(n for n in names if n)


def _land_size(raw: dict) -> str:
    land = _g(raw, "propertySizes", "land", default=None) or {}
    disp = land.get("displayValue") or land.get("value") or ""
    unit = _g(land, "sizeUnit", "displayValue") or _g(land, "sizeUnit", "id") or ""
    if disp and unit:
        return f"{disp} {unit}".strip()
    return str(disp or raw.get("landSize") or "")


def _canonical_url(raw: dict) -> str:
    href = _g(raw, "_links", "canonical", "href") or _g(raw, "_links", "canonical")
    if isinstance(href, str) and href and "{" not in href:
        if href.startswith("http"):
            return href
        return f"https://www.example-portal.example{href}"
    # Do not guess from an id: live data (2026-08-30) showed those fallback
    # links are dead. Empty -> validation drops the row.
    return ""


def _price_text(raw: dict) -> str:
    return (
        _g(raw, "price", "display")
        or _g(raw, "priceDetails", "displayPrice")
        or _g(raw, "priceDetails", "price")
        or raw.get("displayPrice")
        or ""
    )


def map_listing(raw: dict) -> Listing:
    """Map one raw listing dict to a ``Listing``."""
    price_text = _price_text(raw)
    price_value = _g(raw, "price", "value")
    if isinstance(price_value, bool) or not isinstance(price_value, int | float):
        price_value = None
    if price_value is not None and price_value <= 0:
        price_value = None
    if price_value is None:
        price_value = parse_price_value(price_text)

    property_type = (
        _g(raw, "propertyType", "display") or _g(raw, "propertyType", "id") or ""
    )

    return Listing(
        listing_url=_canonical_url(raw),
        address_full=(
            _g(raw, "address", "display", "fullAddress")
            or _g(raw, "address", "display", "shortAddress")
            or _g(raw, "address", "fullAddress")
            or ""
        ),
        suburb=_g(raw, "address", "suburb") or "",
        state=(_g(raw, "address", "state") or "").upper(),
        postcode=str(_g(raw, "address", "postcode") or ""),
        price_text=price_text,
        price_value=price_value,
        property_type=property_type,
        bedrooms=_feature(raw, "bedrooms"),
        bathrooms=_feature(raw, "bathrooms"),
        car_spaces=_feature(raw, "parkingSpaces"),
        land_size=_land_size(raw),
        description=(raw.get("description") or "").strip(),
        agent_name=_agents(raw),
        agency_name=(
            _g(raw, "listingCompany", "name")
            or _g(raw, "advertising", "agency", "name")
            or ""
        ),
        listing_date=(
            raw.get("dateListed")
            or _g(raw, "dateListed", "value")
            or raw.get("listingDateDisplay")
            or ""
        ),
        image_urls=_images(raw),
        listing_kind=listing_kind(raw),
    )
