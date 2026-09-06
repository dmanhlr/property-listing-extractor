"""Parity: the Python parser and the JS parser must agree, row for row.

For every fixture page this runs ``node extension/parser.js <file>`` and compares
the JSON it prints against ``map_listing`` over the same page. If Node is not on
PATH the test skips with a clear message -- it never passes silently.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

from listing_extractor.blob import extract_blob, iter_listings
from listing_extractor.mapping import map_listing
from listing_extractor.schema import FIELDNAMES

REPO_ROOT = Path(__file__).resolve().parents[1]
PARSER_JS = REPO_ROOT / "extension" / "parser.js"
PAGES = sorted((REPO_ROOT / "tests" / "fixtures" / "pages").glob("*.html"))

NODE = shutil.which("node")


def _normalise(rows: list[dict]) -> list[dict]:
    """Keep only exported fields; make integral floats compare equal to ints."""
    out = []
    for row in rows:
        clean = {}
        for key in FIELDNAMES:
            value = row.get(key)
            if isinstance(value, float) and value.is_integer():
                value = int(value)
            clean[key] = value
        out.append(clean)
    return out


def _python_rows(html: str) -> list[dict]:
    return _normalise(
        [map_listing(raw).as_row() for raw in iter_listings(extract_blob(html))]
    )


def _node_rows(path: Path) -> list[dict]:
    proc = subprocess.run(
        [NODE, str(PARSER_JS), str(path)],
        capture_output=True,
        timeout=60,
    )
    if proc.returncode != 0:
        stderr = proc.stderr.decode("utf-8", "replace")
        raise AssertionError(f"node parser failed ({proc.returncode}): {stderr}")
    return _normalise(json.loads(proc.stdout.decode("utf-8")))


@pytest.mark.skipif(NODE is None, reason="node not on PATH; parity test needs Node.js")
@pytest.mark.parametrize("page", PAGES, ids=[p.name for p in PAGES])
def test_python_and_js_parsers_agree(page: Path):
    html = page.read_text(encoding="utf-8")
    py_rows = _python_rows(html)
    js_rows = _node_rows(page)
    assert [r["listing_url"] for r in js_rows] == [r["listing_url"] for r in py_rows]
    assert js_rows == py_rows


@pytest.mark.skipif(NODE is None, reason="node not on PATH; parity test needs Node.js")
def test_parser_js_is_present():
    assert PARSER_JS.is_file()


def test_fixture_pages_exist():
    # Guards against an empty parametrize list quietly making parity a no-op.
    assert len(PAGES) >= 3
