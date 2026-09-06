"""Render the exported sheet to ``docs/output_preview.png`` (the README hero).

Parses the bundled fixtures in-process, then screenshots the first rows as a
styled table with Playwright's bundled Chromium.

    python scripts/render_preview.py

Needs the ``playwright`` extra: ``pip install -e ".[playwright]"`` then
``playwright install chromium``.
"""

from __future__ import annotations

import html
from pathlib import Path

from listing_extractor.blob import extract_blob, iter_listings
from listing_extractor.mapping import map_listing
from listing_extractor.validate import validate_rows

REPO_ROOT = Path(__file__).resolve().parents[1]
PAGES_DIR = REPO_ROOT / "tests" / "fixtures" / "pages"
OUT_PNG = REPO_ROOT / "docs" / "output_preview.png"

MAX_ROWS = 12
COLUMNS = [
    ("suburb", "Suburb"),
    ("state", "St"),
    ("postcode", "PC"),
    ("price_text", "Price"),
    ("price_value", "Price value"),
    ("property_type", "Type"),
    ("bedrooms", "Bd"),
    ("bathrooms", "Ba"),
    ("car_spaces", "Car"),
    ("land_size", "Land"),
    ("listing_url", "Listing URL"),
]


def _rows() -> list:
    listings = []
    for page in sorted(PAGES_DIR.glob("search-*.html")):
        blob = extract_blob(page.read_text(encoding="utf-8"))
        listings += [map_listing(raw) for raw in iter_listings(blob)]
    valid = validate_rows(listings).valid

    # Order the preview so the interesting rows are visible: a project (range
    # price, empty beds), a "Contact Agent" row and a hidden-address row show
    # up alongside ordinary listings rather than being paginated off-screen.
    def interesting(listing) -> bool:
        return (
            listing.listing_kind == "project"
            or listing.price_value is None
            or not listing.address_full
        )

    special = [x for x in valid if interesting(x)]
    plain = [x for x in valid if not interesting(x)]
    return plain[:7] + special + plain[7:]


def _cell(listing, key: str) -> str:
    value = getattr(listing, key)
    if value is None or value == "":
        return "<span class='empty'>—</span>"
    if key == "listing_url":
        # The offline demo keeps canonical links relative (no origin context);
        # the real routes absolutise them against the tab / page origin.
        return html.escape("…" + value if value.startswith("/") else value)
    if key == "price_value":
        return f"{int(value):,}"
    return html.escape(str(value))


def _table_html(rows: list) -> str:
    head = "".join(f"<th>{html.escape(label)}</th>" for _, label in COLUMNS)
    body = ""
    for listing in rows[:MAX_ROWS]:
        tds = "".join(f"<td>{_cell(listing, key)}</td>" for key, _ in COLUMNS)
        body += f"<tr>{tds}</tr>"
    total = len(rows)
    font_stack = '13px -apple-system, "Segoe UI", Roboto, Arial, sans-serif'
    caption = (
        f"listings.csv &nbsp;<span>— {MAX_ROWS} of {total} valid rows, "
        "fixture-verified (this build)</span>"
    )
    return f"""<!doctype html><meta charset="utf-8">
<style>
  body {{ margin: 0; padding: 24px; background: #eef1f4;
         font: {font_stack}; color: #1a1a1a; }}
  .card {{ background: #fff; border-radius: 10px;
          box-shadow: 0 4px 20px rgba(0,0,0,.10);
          overflow: hidden; display: inline-block; }}
  .cap {{ padding: 12px 16px; font-weight: 700;
         border-bottom: 1px solid #e5e7eb; }}
  .cap span {{ font-weight: 400; color: #6b7280; }}
  table {{ border-collapse: collapse; }}
  th, td {{ padding: 7px 12px; text-align: left; white-space: nowrap;
           border-bottom: 1px solid #f0f2f4; }}
  th {{ background: #f8fafc; color: #374151; font-size: 11px;
       text-transform: uppercase; letter-spacing: .04em; }}
  td {{ font-variant-numeric: tabular-nums; }}
  tr:last-child td {{ border-bottom: none; }}
  .empty {{ color: #cbd5e1; }}
</style>
<div class="card">
  <div class="cap">{caption}</div>
  <table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table>
</div>
"""


def main() -> None:
    from playwright.sync_api import sync_playwright

    rows = _rows()
    OUT_PNG.parent.mkdir(parents=True, exist_ok=True)
    page_html = _table_html(rows)

    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        page = browser.new_page(
            viewport={"width": 1400, "height": 700}, device_scale_factor=2
        )
        page.set_content(page_html, wait_until="networkidle")
        card = page.locator(".card")
        card.screenshot(path=str(OUT_PNG))
        browser.close()
    print(f"wrote {OUT_PNG}")


if __name__ == "__main__":
    main()
