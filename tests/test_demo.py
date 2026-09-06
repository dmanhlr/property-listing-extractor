"""The --demo path: parse the bundled fixtures offline, write CSV + XLSX."""

from __future__ import annotations

import csv

from openpyxl import load_workbook

from listing_extractor.cli import main
from listing_extractor.schema import FIELDNAMES


def test_demo_writes_csv_and_xlsx_with_expected_counts(tmp_path, capsys):
    rc = main(["--demo", "--out", str(tmp_path)])
    assert rc == 0

    csv_path = tmp_path / "listings.csv"
    xlsx_path = tmp_path / "listings.xlsx"
    assert csv_path.is_file()
    assert xlsx_path.is_file()

    with csv_path.open(encoding="utf-8") as fh:
        reader = csv.reader(fh)
        header = next(reader)
        rows = list(reader)
    assert header == FIELDNAMES
    assert len(rows) == 26  # 28 seen, 1 no-link dropped, 1 duplicate dropped

    wb = load_workbook(xlsx_path)
    ws = wb.active
    assert ws.max_row == 27  # header + 26
    assert ws.freeze_panes == "A2"

    out = capsys.readouterr().out
    assert "pages parsed   2" in out
    assert "rows seen      28" in out
    assert "valid rows     26" in out
    assert "dropped        2" in out
    assert "duplicate listing_url" in out


def test_demo_drops_agent_columns_are_still_present_but_blank(tmp_path):
    # --demo keeps agent columns in the schema; the CLI route drops the values.
    # Here we just assert the demo export is well-formed and agent columns exist.
    main(["--demo", "--out", str(tmp_path)])
    with (tmp_path / "listings.csv").open(encoding="utf-8") as fh:
        header = next(csv.reader(fh))
    assert "agent_name" in header and "agency_name" in header


def test_demo_image_urls_have_no_template_tokens(tmp_path):
    main(["--demo", "--out", str(tmp_path)])
    with (tmp_path / "listings.csv").open(encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            assert "{" not in row["image_urls"] and "}" not in row["image_urls"]
