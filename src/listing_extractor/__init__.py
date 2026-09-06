"""Extract clean listing rows from a bot-protected property portal.

Two runtimes share one parser:
  * the Chrome extension (``extension/parser.js``), driven by a person browsing;
  * the Playwright route (``listing_extractor.routes.playwright_route``), which
    needs an Australian residential proxy.

This package is the Python side. ``blob`` finds and un-stringifies the embedded
JSON, ``shape`` decides what is a listing, ``mapping`` turns a raw dict into a
``Listing``, ``validate`` drops rows that fail the required-field check, and
``export`` writes CSV + XLSX.
"""

from listing_extractor.schema import FIELDNAMES, REQUIRED_FIELDS

__all__ = [
    "FIELDNAMES",
    "REQUIRED_FIELDS",
    "Listing",
    "map_listing",
    "validate_rows",
    "ValidationResult",
]


def __getattr__(name: str):  # lazy re-exports, avoids an import cycle at load
    if name in ("Listing", "map_listing"):
        from listing_extractor import mapping

        return getattr(mapping, name)
    if name in ("validate_rows", "ValidationResult"):
        from listing_extractor import validate

        return getattr(validate, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
