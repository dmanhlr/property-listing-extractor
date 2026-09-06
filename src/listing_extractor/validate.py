"""Required-field check and de-dupe, with a drop log that gives reasons.

Never repair a row. A field the source did not expose stays empty; a row that
fails the check is dropped and the reason is recorded.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from listing_extractor.mapping import Listing
from listing_extractor.schema import REQUIRED_FIELDS


@dataclass
class DropRecord:
    """One dropped row and why."""

    listing_url: str
    reason: str


@dataclass
class ValidationResult:
    valid: list[Listing] = field(default_factory=list)
    dropped: list[DropRecord] = field(default_factory=list)

    @property
    def seen(self) -> int:
        return len(self.valid) + len(self.dropped)

    def reason_counts(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for d in self.dropped:
            counts[d.reason] = counts.get(d.reason, 0) + 1
        return counts


def _missing_fields(listing: Listing) -> list[str]:
    missing = []
    for name in REQUIRED_FIELDS:
        value = getattr(listing, name)
        if value is None or (isinstance(value, str) and not value.strip()):
            missing.append(name)
    return missing


def validate_rows(listings: list[Listing]) -> ValidationResult:
    """Split ``listings`` into valid rows and dropped rows.

    Drop reasons:
      * ``missing required: <fields>`` -- one or more required fields empty
        (covers regressions 2 and 4: no canonical link, hidden street address
        that also loses suburb/state/postcode).
      * ``duplicate listing_url`` -- a later row repeats an already-kept URL
        (the same listing showing up on two search pages).
    """
    result = ValidationResult()
    seen_urls: set[str] = set()
    for listing in listings:
        missing = _missing_fields(listing)
        if missing:
            result.dropped.append(
                DropRecord(
                    listing.listing_url, f"missing required: {', '.join(missing)}"
                )
            )
            continue
        if listing.listing_url in seen_urls:
            result.dropped.append(
                DropRecord(listing.listing_url, "duplicate listing_url")
            )
            continue
        seen_urls.add(listing.listing_url)
        result.valid.append(listing)
    return result
