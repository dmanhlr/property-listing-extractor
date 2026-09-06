"""``listing-extract`` command line.

    listing-extract --demo
    listing-extract --suburb "Richmond, VIC 3121" [--channel buy] [--pages N]
                    [--proxy URL] [--keep-agent] [--out DIR] [--dry-run]

``--demo`` parses the bundled fixture pages offline and writes
``output/listings.csv`` + ``.xlsx`` with a summary. Any other run uses the
Playwright route, which needs an Australian residential proxy for live loads;
``--dry-run`` just prints the URLs it would visit.
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
from pathlib import Path

from listing_extractor.blob import extract_blob, iter_listings
from listing_extractor.export import write_both
from listing_extractor.mapping import Listing, map_listing
from listing_extractor.schema import REQUIRED_FIELDS
from listing_extractor.validate import ValidationResult, validate_rows

log = logging.getLogger("listing_extractor")


def _find_fixture_dir() -> Path:
    """Locate ``tests/fixtures/pages`` from an env var or by walking up."""
    env = os.environ.get("LISTING_EXTRACTOR_FIXTURES")
    if env:
        p = Path(env)
        if p.is_dir():
            return p
        raise SystemExit(f"LISTING_EXTRACTOR_FIXTURES is not a directory: {p}")
    here = Path(__file__).resolve()
    for parent in [here, *here.parents]:
        candidate = parent / "tests" / "fixtures" / "pages"
        if candidate.is_dir():
            return candidate
    raise SystemExit(
        "demo fixtures not found. Run from a clone of the repo, or set "
        "LISTING_EXTRACTOR_FIXTURES to tests/fixtures/pages."
    )


def _drop_agents(listings: list[Listing]) -> None:
    for listing in listings:
        listing.agent_name = ""
        listing.agency_name = ""


def _parse_html_files(paths: list[Path]) -> tuple[int, list[Listing]]:
    """Return (pages parsed, listings mapped) for a list of HTML files."""
    listings: list[Listing] = []
    for path in paths:
        html = path.read_text(encoding="utf-8")
        blob = extract_blob(html)
        page_listings = [map_listing(raw) for raw in iter_listings(blob)]
        log.info("%s: %s listings", path.name, len(page_listings))
        listings.extend(page_listings)
    return len(paths), listings


def _print_summary(
    pages: int, seen: int, result: ValidationResult, csv_path: Path, xlsx_path: Path
) -> None:
    print()
    print("summary")
    print(f"  pages parsed   {pages}")
    print(f"  rows seen      {seen}")
    print(f"  valid rows     {len(result.valid)}")
    print(f"  dropped        {len(result.dropped)}")
    for reason, count in sorted(result.reason_counts().items()):
        print(f"    - {count}x {reason}")
    kinds: dict[str, int] = {}
    for listing in result.valid:
        kinds[listing.listing_kind] = kinds.get(listing.listing_kind, 0) + 1
    if kinds:
        breakdown = ", ".join(f"{v} {k}" for k, v in sorted(kinds.items()))
        print(f"  valid by kind  {breakdown}")
    print(f"  required fields  {', '.join(REQUIRED_FIELDS)}")
    print(f"  wrote  {csv_path}")
    print(f"  wrote  {xlsx_path}")


def _run_demo(out_dir: Path) -> int:
    fixture_dir = _find_fixture_dir()
    # The job this solves is a one-time export from search-result pages. Detail
    # pages are kept in the fixture set for parser parity, not for this flow.
    paths = sorted(fixture_dir.glob("search-*.html"))
    if not paths:
        raise SystemExit(f"no search fixture pages in {fixture_dir}")
    pages, listings = _parse_html_files(paths)
    result = validate_rows(listings)
    csv_path, xlsx_path = write_both(result.valid, out_dir)
    _print_summary(pages, len(listings), result, csv_path, xlsx_path)
    return 0


def _run_route(args: argparse.Namespace) -> int:
    from listing_extractor.routes.playwright_route import RouteConfig, run

    config = RouteConfig(
        suburb=args.suburb,
        channel=args.channel,
        pages=args.pages,
        proxy=args.proxy,
    )
    result = run(config, dry_run=args.dry_run)
    if args.dry_run:
        print(f"\n{len(result.urls_visited)} URLs planned (no browser opened)")
        return 0

    listings = result.listings
    if not args.keep_agent:
        _drop_agents(listings)
    validation = validate_rows(listings)
    csv_path, xlsx_path = write_both(validation.valid, Path(args.out))
    _print_summary(
        len(result.urls_visited), len(listings), validation, csv_path, xlsx_path
    )
    if result.blocked_urls:
        print(f"  blocked        {len(result.blocked_urls)}")
        for url in result.blocked_urls:
            print(f"    - {url}")
    if result.stopped_early:
        print(f"  stopped early  {result.stop_reason}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="listing-extract",
        description="Extract property listings to CSV + XLSX.",
    )
    parser.add_argument(
        "--demo",
        action="store_true",
        help="parse the bundled fixture pages offline and exit",
    )
    parser.add_argument("--suburb", help='e.g. "Richmond, VIC 3121"')
    parser.add_argument(
        "--channel", default="buy", choices=("buy", "rent", "sold"), help="default: buy"
    )
    parser.add_argument("--pages", type=int, default=5, help="max search pages")
    parser.add_argument("--proxy", help="AU residential proxy; overrides PROXY_URL")
    parser.add_argument(
        "--keep-agent",
        action="store_true",
        help="keep agent_name / agency_name (dropped by default)",
    )
    parser.add_argument("--out", default="output", help="output directory")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="print the URLs the route would visit; open no browser",
    )
    parser.add_argument("-v", "--verbose", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    logging.basicConfig(
        level=logging.INFO if args.verbose else logging.WARNING,
        format="%(levelname)s %(name)s: %(message)s",
    )

    if args.demo:
        return _run_demo(Path(args.out))
    if not args.suburb:
        build_parser().error("either --demo or --suburb is required")
    return _run_route(args)


if __name__ == "__main__":
    sys.exit(main())
