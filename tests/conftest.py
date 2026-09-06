"""Shared fixtures: paths to the synthetic pages and their parsed rows."""

from __future__ import annotations

from pathlib import Path

import pytest

from listing_extractor.blob import extract_blob, iter_listings
from listing_extractor.mapping import Listing, map_listing

PAGES_DIR = Path(__file__).parent / "fixtures" / "pages"
SEARCH_PAGE_1 = PAGES_DIR / "search-buy-riverbend-1.html"
SEARCH_PAGE_2 = PAGES_DIR / "search-buy-riverbend-2.html"
DETAIL_PAGE = PAGES_DIR / "detail-buy-riverbend-house.html"


def parse_page(path: Path) -> list[Listing]:
    html = path.read_text(encoding="utf-8")
    return [map_listing(raw) for raw in iter_listings(extract_blob(html))]


@pytest.fixture(scope="session")
def pages_dir() -> Path:
    return PAGES_DIR


@pytest.fixture(scope="session")
def search_page_1() -> list[Listing]:
    return parse_page(SEARCH_PAGE_1)


@pytest.fixture(scope="session")
def search_page_2() -> list[Listing]:
    return parse_page(SEARCH_PAGE_2)


@pytest.fixture(scope="session")
def all_search_listings() -> list[Listing]:
    return parse_page(SEARCH_PAGE_1) + parse_page(SEARCH_PAGE_2)


def by_id(listings: list[Listing], listing_id: str) -> Listing:
    """Find a mapped row by the id embedded in its canonical URL."""
    for listing in listings:
        if listing.listing_url.endswith(listing_id):
            return listing
    raise AssertionError(f"no listing ending {listing_id!r}")
