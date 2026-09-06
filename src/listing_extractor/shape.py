"""Decide whether a raw dict is a listing, and what kind.

Regression 1 (live data, 2026-08-30): the shape test accepted any object with
``address`` + ``media``, so agency office cards leaked in -- 23 of 53 rows. The
fix: require ``address.suburb`` (office blobs have an ``address`` but no suburb
breakdown) and drop ``media`` from the test entirely (agency cards carry a logo
image too).
"""

from __future__ import annotations

from typing import Any

# A listing must have at least one of these id-ish markers ...
_ID_KEYS = ("listingId", "id")
# ... and at least one of these shape markers.
_SHAPE_KEYS = ("propertyType", "generalFeatures", "productDepth", "price")

# property_type / channel strings that mark a multi-unit development. These
# price per unit as a range and carry no single bed/bath count (regression 3).
_PROJECT_HINTS = (
    "project",
    "new apartments",
    "new apartment",
    "new land",
    "development",
)


def _get(d: Any, *path: str) -> Any:
    cur = d
    for p in path:
        if not isinstance(cur, dict):
            return None
        cur = cur.get(p)
        if cur is None:
            return None
    return cur


def looks_like_listing(d: Any) -> bool:
    """True if ``d`` is shaped like a property listing.

    Requires an ``address`` dict *with a suburb*, an id marker, and a shape
    marker. ``media`` is deliberately not part of the test.
    """
    if not isinstance(d, dict):
        return False
    addr = d.get("address")
    if not isinstance(addr, dict):
        return False
    if not addr.get("suburb"):
        return False
    has_id = any(k in d for k in _ID_KEYS) or isinstance(d.get("_links"), dict)
    has_shape = any(k in d for k in _SHAPE_KEYS)
    return has_id and has_shape


def listing_key(d: dict) -> str:
    """Stable de-dupe key for a raw listing dict."""
    return str(d.get("listingId") or d.get("id") or id(d))


def listing_kind(d: dict) -> str:
    """``"project"`` for a multi-unit development, else ``"standard"``.

    Detected from the property-type text and the channel, not from a dedicated
    field -- the portal does not expose one consistently.
    """
    hay = " ".join(
        str(x).lower()
        for x in (
            _get(d, "propertyType", "display"),
            _get(d, "propertyType", "id"),
            d.get("channel"),
            d.get("productType"),
        )
        if x
    )
    if any(h in hay for h in _PROJECT_HINTS):
        return "project"
    return "standard"
