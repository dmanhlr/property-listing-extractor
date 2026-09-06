"""playwright_route.py with a fake fetcher -- no browser, no network.

Covers the search-URL builder, pagination driven by the discovered max-page,
the retry/backoff path, and the "stop after N consecutive blocks" safeguard.
"""

from __future__ import annotations

import json

import pytest

from listing_extractor.routes.playwright_route import (
    RouteConfig,
    build_search_url,
    collect,
    looks_blocked,
    planned_urls,
    run,
    slugify_suburb,
)

APP_KEY = "resi-property_listing-experience-web"


def _page_html(items: list[dict], max_page: int) -> str:
    data = json.dumps(
        {
            "s": {
                "results": {
                    "exact": {"items": items},
                    "pagination": {"maxPageNumberAvailable": max_page},
                }
            }
        }
    )
    cache = json.dumps({"q": {"data": data}})
    blob = json.dumps({APP_KEY: {"urqlClientCache": cache}})
    return f"<script>window.ArgonautExchange = {blob};</script>"


def _listing(n: int) -> dict:
    return {
        "listingId": str(n),
        "_links": {"canonical": {"href": f"/property-house-vic-x-{n}"}},
        "address": {"suburb": "Riverbend", "state": "vic", "postcode": "3999"},
        "propertyType": {"display": "House"},
        "price": {"display": "$1,000,000", "value": 1_000_000},
    }


def _no_sleep(_config):
    return None


# --- URL building ---------------------------------------------------------


def test_slugify_suburb_variants():
    assert slugify_suburb("Richmond, VIC 3121") == "richmond+vic+3121"
    assert slugify_suburb("Richmond VIC 3121") == "richmond+vic+3121"


def test_build_search_url_by_channel():
    assert build_search_url("buy", "Richmond, VIC 3121", 1).endswith(
        "/buy/in-richmond+vic+3121/list-1"
    )
    assert build_search_url("rent", "Bondi, NSW 2026", 3).endswith(
        "/rent/in-bondi+nsw+2026/list-3"
    )


def test_build_search_url_rejects_bad_channel():
    with pytest.raises(ValueError):
        build_search_url("lease", "X", 1)


def test_planned_urls_respects_page_cap():
    cfg = RouteConfig(suburb="Richmond, VIC 3121", pages=4)
    assert planned_urls(cfg) == [
        build_search_url("buy", "Richmond, VIC 3121", p) for p in range(1, 5)
    ]


# --- block detection ----------------------------------------------------


def test_looks_blocked_on_status_and_markers():
    assert looks_blocked(429, "whatever")
    assert looks_blocked(200, "<h1>Pardon Our Interruption</h1>")
    assert looks_blocked(200, "tiny body")  # < 1500 chars, no blob
    assert not looks_blocked(200, _page_html([_listing(1)], 1))


# --- collect() with a fake fetcher -----------------------------------


def test_collect_paginates_to_discovered_max():
    pages = {
        1: (200, _page_html([_listing(1), _listing(2)], 3)),
        2: (200, _page_html([_listing(3)], 3)),
        3: (200, _page_html([_listing(4)], 3)),
        4: (200, _page_html([_listing(5)], 3)),
    }
    visited = []

    def fetcher(url: str):
        page = int(url.rsplit("-", 1)[1])
        visited.append(page)
        return pages[page]

    cfg = RouteConfig(suburb="Richmond, VIC 3121", pages=10)
    result = collect(cfg, fetcher, sleep=_no_sleep)

    assert visited == [1, 2, 3]  # capped at maxPageNumberAvailable = 3
    assert len(result.listings) == 4
    assert result.blocked_urls == []
    assert not result.stopped_early
    # relative canonical hrefs are absolutised against the search page origin
    assert result.listings[0].listing_url.startswith(
        "https://www.example-portal.example/property-house-vic-x-"
    )


def test_collect_stops_after_consecutive_blocks():
    def fetcher(_url: str):
        return (429, "blocked")

    cfg = RouteConfig(
        suburb="Richmond, VIC 3121",
        pages=10,
        retries=0,
        max_consecutive_blocks=3,
    )
    result = collect(cfg, fetcher, sleep=_no_sleep)

    assert result.stopped_early
    assert "consecutive blocked pages" in result.stop_reason
    assert len(result.blocked_urls) == 3
    assert result.listings == []


def test_collect_retries_then_succeeds():
    calls = {"n": 0}

    def fetcher(url: str):
        calls["n"] += 1
        if calls["n"] == 1:
            return (403, "denied")
        return (200, _page_html([_listing(1)], 1))

    cfg = RouteConfig(suburb="Richmond, VIC 3121", pages=1, retries=2)
    # patch the module's backoff sleep so the test is fast
    import listing_extractor.routes.playwright_route as mod

    mod.time.sleep = lambda *_: None
    result = collect(cfg, fetcher, sleep=_no_sleep)
    assert len(result.listings) == 1
    assert result.blocked_urls == []


# --- run(dry_run=True) -------------------------------------------------


def test_run_dry_run_prints_urls_and_opens_no_browser(capsys):
    cfg = RouteConfig(suburb="Richmond, VIC 3121", pages=3)
    result = run(cfg, dry_run=True)
    out = capsys.readouterr().out.strip().splitlines()
    assert out == planned_urls(cfg)
    assert result.listings == []
    assert result.urls_visited == planned_urls(cfg)
