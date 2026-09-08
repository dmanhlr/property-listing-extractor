# Publishing checklist

This repo is committed locally only. Nothing here pushes to GitHub — you do that.

## 1. Create the repo (when ready)

```bash
gh repo create property-listing-extractor \
  --public \
  --source . \
  --remote origin \
  --description "Export clean listing rows from a bot-protected property portal: a Chrome extension for browsing plus a proxy-gated Playwright route, one shared parser tested to agree." \
  --push
```

Topics (set after creating):

```bash
gh repo edit --add-topic chrome-extension,manifest-v3,playwright,web-scraping,csv-export,python,real-estate,data-extraction
```

## 2. Node (for the parity test)

`tests/test_parity.py` runs the Python parser and `node extension/parser.js`
over every fixture and compares the rows. **CI runs it regardless** — the
workflow installs Node 20. To run it locally, install Node (≥ 18) from
<https://nodejs.org/>; without `node` on PATH the test skips with a clear
message instead of passing silently.

## 3. Manual step — re-verify the parser against the live site (required)

The parser was rewritten in this build. It is verified against the structural
fixtures and by the parity test, but not yet against the live portal. Do one
manual collection before treating any live number as delivered.

1. `pip install -e ".[dev]"`; install Node so the parity test runs locally too.
2. Load `extension/` unpacked in Chrome (`extension/README.md`). No file edits
   are needed — the extension asks for site access at runtime.
3. Open the portal, open the popup, click **Grant access to this site**.
4. Browse the same suburb search used on 2026-08-30 (or the client's list).
   Click **Scan this page** on each results page. Do not automate.
5. **Export CSV.** Record, keeping "seen" and "exported" apart:
   - **seen** — the running "Scanned N" tally across all pages.
   - **exported** — rows in the CSV. The store is keyed by `listing_url`, so
     this equals the unique-URL count; `seen − exported` is duplicates plus
     rows with no canonical link.
   - **agency cards** in the export (expect 0).
   - **fabricated / malformed URLs** (expect 0 — the parser only emits a
     canonical link the page carried).
   - **exported URLs that return 404 when visited** — expect a few. A listing
     can be withdrawn between collection and checking; this is not a defect.
     Keep it separate from the fabricated-URL count.
6. Paste them into `README.md`, in the `## Results` section, replacing the
   previous "Live re-verification" block. Label every number (seen / exported /
   unique / agency cards / fabricated URLs / 404 at check time) — do not print a
   bare "N rows, M unique URLs" line.

   If `exported`, agency cards, or fabricated URLs drift far from the
   predecessor's 26 / 0 / 0, open an issue before publishing. A handful of 404s
   is expected and does not block publishing.

## 4. Other manual steps

- **Playwright route, live:** set an Australian residential proxy in `PROXY_URL`
  (see `.env.example`) and the base URL that route navigates. Untested end to
  end — treat a first live run as exploratory. Run
  `listing-extract --suburb "..." --dry-run` first to see the URLs.
- **Demo GIF (optional):** `docs/RECORD_GIF.md`. Save as `docs/demo.gif`, add it
  under the hero image in `README.md`.
- **License holder:** `LICENSE` says "Manh" — change if you want your full name.
- **Screenshots:** `docs/extension_panel.png` and `docs/extension_popup.png`
  were produced this build against local fixtures. Re-take only if the
  panel/popup UI changes (`python scripts/serve_fixtures.py`, then screenshot).

## 5. Before pushing

```bash
pip install -e ".[dev]"
ruff format --check .
ruff check .
python scripts/check_no_pii.py
pytest                 # 55 with Node; 51 pass + 4 skip without (parity)
```
