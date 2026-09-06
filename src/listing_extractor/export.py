"""Write listing rows to CSV and XLSX.

CSV joins ``image_urls`` with ``;``. XLSX gets a frozen header row and an
autofilter. ``price_value`` is written as a number when present, blank when not.
"""

from __future__ import annotations

import csv
from pathlib import Path

from openpyxl import Workbook

from listing_extractor.mapping import Listing
from listing_extractor.schema import FIELDNAMES


def _cell(name: str, value: object) -> object:
    if name == "image_urls" and isinstance(value, list):
        return ";".join(value)
    if value is None:
        return ""
    return value


def write_csv(listings: list[Listing], path: str | Path) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(FIELDNAMES)
        for listing in listings:
            row = listing.as_row()
            writer.writerow([_cell(name, row[name]) for name in FIELDNAMES])
    return path


def write_xlsx(listings: list[Listing], path: str | Path) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    wb = Workbook()
    ws = wb.active
    ws.title = "listings"
    ws.append(FIELDNAMES)
    for listing in listings:
        row = listing.as_row()
        ws.append([_cell(name, row[name]) for name in FIELDNAMES])
    ws.freeze_panes = "A2"
    last_col = chr(ord("A") + len(FIELDNAMES) - 1)
    ws.auto_filter.ref = f"A1:{last_col}{ws.max_row}"
    wb.save(path)
    return path


def write_both(
    listings: list[Listing], out_dir: str | Path, stem: str = "listings"
) -> tuple[Path, Path]:
    out_dir = Path(out_dir)
    csv_path = write_csv(listings, out_dir / f"{stem}.csv")
    xlsx_path = write_xlsx(listings, out_dir / f"{stem}.xlsx")
    return csv_path, xlsx_path
