"""Volume route: drive a real browser through search pages, parse each blob.

This route needs an Australian residential proxy. Automated page loads from
non-AU IPs get 429/403 on the first request (the portal is behind Kasada: TLS
fingerprinting, a JS challenge, a geo filter, rate limits). The predecessor
prototype never completed this route end to end for that reason.

Safeguards built in:
  * randomised delay between requests;
  * retry with growing backoff on a blocked response;
  * stop the whole run after N consecutive blocked pages;
  * every blocked URL is listed in the summary.

``--dry-run`` prints the URLs the route would visit and opens no browser, so the
pagination and URL building are testable without a proxy.
"""

from __future__ import annotations

import logging
import os
import random
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from urllib.parse import quote

from listing_extractor.blob import extract_blob, find_max_page, iter_listings
from listing_extractor.mapping import Listing, map_listing

log = logging.getLogger(__name__)

BASE_URL = "https://www.example-portal.example"
CHANNELS = ("buy", "rent", "sold")

# A fetched page that looks like an anti-bot wall.
_BLOCK_STATUSES = {403, 429, 503}
_BLOCK_MARKERS = (
    "pardon our interruption",
    "request rejected",
    "access to this page has been denied",
    "unusual activity",
    "verify you are a human",
)


class Blocked(RuntimeError):
    """Raised when a fetched page looks like an anti-bot wall."""


def slugify_suburb(raw: str) -> str:
    """``"Richmond, VIC 3121"`` -> ``"richmond+vic+3121"`` (URL segment).

    Accepts ``"Richmond VIC 3121"`` too. Percent-encodes anything unexpected.
    """
    text = raw.replace(",", " ")
    parts = [p for p in text.split() if p]
    return quote("+".join(p.lower() for p in parts), safe="+")


def _origin(url: str) -> str:
    from urllib.parse import urlparse

    p = urlparse(url)
    return f"{p.scheme}://{p.netloc}" if p.scheme and p.netloc else ""


def build_search_url(channel: str, suburb: str, page: int) -> str:
    channel = channel.lower().strip()
    if channel not in CHANNELS:
        raise ValueError(f"channel must be one of {CHANNELS}, got {channel!r}")
    seg = slugify_suburb(suburb)
    if page <= 1:
        return f"{BASE_URL}/{channel}/in-{seg}/list-1"
    return f"{BASE_URL}/{channel}/in-{seg}/list-{page}"


@dataclass
class RouteConfig:
    suburb: str
    channel: str = "buy"
    pages: int = 5  # hard cap; the real page count comes from the first page
    proxy: str | None = None
    min_delay: float = 2.0
    max_delay: float = 6.0
    retries: int = 2  # extra attempts per blocked page
    max_consecutive_blocks: int = 3  # stop the run after this many in a row

    def __post_init__(self) -> None:
        self.channel = self.channel.lower().strip()
        if self.channel not in CHANNELS:
            raise ValueError(f"channel must be one of {CHANNELS}, got {self.channel!r}")
        if self.proxy is None:
            self.proxy = os.environ.get("PROXY_URL") or None


@dataclass
class RouteResult:
    urls_visited: list[str] = field(default_factory=list)
    blocked_urls: list[str] = field(default_factory=list)
    listings: list[Listing] = field(default_factory=list)
    stopped_early: bool = False
    stop_reason: str = ""


def planned_urls(config: RouteConfig) -> list[str]:
    """The URLs the route would visit given the page cap (no network)."""
    return [
        build_search_url(config.channel, config.suburb, p)
        for p in range(1, max(1, config.pages) + 1)
    ]


def looks_blocked(status: int, html: str) -> bool:
    if status in _BLOCK_STATUSES:
        return True
    low = html[:8000].lower()
    if any(m in low for m in _BLOCK_MARKERS):
        return True
    # A tiny body with no blob is almost always a challenge page.
    if len(html) < 1500 and "argonautexchange" not in low:
        return True
    return False


# A fetcher takes a URL and returns ``(status_code, html)``.
Fetcher = Callable[[str], "tuple[int, str]"]


def _sleep_between(config: RouteConfig) -> None:
    time.sleep(random.uniform(config.min_delay, config.max_delay))


def collect(
    config: RouteConfig,
    fetcher: Fetcher,
    *,
    sleep: Callable[[RouteConfig], None] = _sleep_between,
) -> RouteResult:
    """Walk search pages with ``fetcher``, parsing listings from each blob.

    ``fetcher`` is injected so the route is unit-testable with a fake page. The
    first page decides the real page count (capped by ``config.pages``). The run
    stops after ``config.max_consecutive_blocks`` blocked pages in a row.
    """
    result = RouteResult()
    consecutive_blocks = 0
    page = 1
    hard_cap = max(1, config.pages)
    discovered_max: int | None = None

    while page <= hard_cap:
        url = build_search_url(config.channel, config.suburb, page)
        result.urls_visited.append(url)
        try:
            html = _fetch_with_retry(url, fetcher, config, sleep)
        except Blocked:
            log.warning("blocked: %s", url)
            result.blocked_urls.append(url)
            consecutive_blocks += 1
            if consecutive_blocks >= config.max_consecutive_blocks:
                result.stopped_early = True
                result.stop_reason = (
                    f"{consecutive_blocks} consecutive blocked pages; "
                    "an AU residential proxy is required"
                )
                log.error(result.stop_reason)
                break
            page += 1
            continue

        consecutive_blocks = 0
        blob = extract_blob(html)
        if discovered_max is None:
            discovered_max = find_max_page(blob)
            if discovered_max:
                hard_cap = min(hard_cap, discovered_max)
                log.info("max page available: %s (cap %s)", discovered_max, hard_cap)
        origin = _origin(url)
        page_listings = [
            map_listing(raw, base_url=origin) for raw in iter_listings(blob)
        ]
        log.info("page %s: %s listings", page, len(page_listings))
        result.listings.extend(page_listings)
        page += 1
        if page <= hard_cap:
            sleep(config)

    return result


def _fetch_with_retry(
    url: str,
    fetcher: Fetcher,
    config: RouteConfig,
    sleep: Callable[[RouteConfig], None],
) -> str:
    last_status = 0
    for attempt in range(config.retries + 1):
        status, html = fetcher(url)
        last_status = status
        if not looks_blocked(status, html):
            return html
        if attempt < config.retries:
            # Growing backoff on a block.
            time.sleep(random.uniform(4, 10) * (attempt + 1))
    raise Blocked(f"{last_status} {url}")


class PlaywrightFetcher:
    """Real fetcher: a Chromium context with an AU locale and an optional proxy.

    Imported lazily so the package (and the demo) do not require Playwright.
    """

    def __init__(self, config: RouteConfig, *, headless: bool = True) -> None:
        self.config = config
        self.headless = headless
        self._pw = None
        self._browser = None
        self._context = None

    def __enter__(self) -> PlaywrightFetcher:
        from playwright.sync_api import sync_playwright

        self._pw = sync_playwright().start()
        self._browser = self._pw.chromium.launch(
            headless=self.headless,
            proxy=_proxy_arg(self.config.proxy),
            args=["--disable-blink-features=AutomationControlled"],
        )
        self._context = self._browser.new_context(
            locale="en-AU",
            timezone_id="Australia/Sydney",
            viewport={"width": 1366, "height": 900},
            extra_http_headers={"Accept-Language": "en-AU,en;q=0.9"},
        )
        return self

    def __exit__(self, *exc: object) -> None:
        for obj in (self._context, self._browser):
            try:
                if obj is not None:
                    obj.close()
            except Exception:  # pragma: no cover - teardown best effort
                pass
        try:
            if self._pw is not None:
                self._pw.stop()
        except Exception:  # pragma: no cover
            pass

    def __call__(self, url: str) -> tuple[int, str]:
        page = self._context.new_page()
        try:
            resp = page.goto(url, wait_until="domcontentloaded", timeout=45_000)
            page.wait_for_timeout(random.randint(700, 1800))
            return (resp.status if resp else 0), page.content()
        finally:
            page.close()


def _proxy_arg(proxy: str | None) -> dict | None:
    if not proxy:
        return None
    from urllib.parse import urlparse

    p = urlparse(proxy if "://" in proxy else f"http://{proxy}")
    arg: dict[str, str] = {"server": f"{p.scheme}://{p.hostname}:{p.port}"}
    if p.username:
        arg["username"] = p.username
    if p.password:
        arg["password"] = p.password
    return arg


def run(config: RouteConfig, *, dry_run: bool = False) -> RouteResult:
    """Entry point used by the CLI.

    ``dry_run`` prints the planned URLs and opens no browser. A live run needs
    ``config.proxy`` set to an AU residential proxy.
    """
    if dry_run:
        result = RouteResult(urls_visited=planned_urls(config))
        for url in result.urls_visited:
            print(url)
        return result

    if not config.proxy:
        log.warning(
            "no proxy set (PROXY_URL / --proxy). Live loads are blocked from most IPs."
        )
    with PlaywrightFetcher(config) as fetcher:
        return collect(config, fetcher)
