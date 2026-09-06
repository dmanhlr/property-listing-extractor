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

## 2. `<<FILL>>` items

| Where | What | How |
|---|---|---|
| `README.md`, "Re-verification of this build against the live site" | rows / unique / agency-cards / dead-links from one live extension run | do step 3 below, paste the four numbers, delete the `<<FILL>>` line |
| `extension/manifest.json` | real portal origin | replace `https://www.example-portal.example/*` in `host_permissions`, `content_scripts[0].matches`, and `web_accessible_resources[0].matches` (3 spots) with the real origin; reload the extension. Keep this change local — do not commit the brand name. |
| `src/listing_extractor/mapping.py` and `extension/parser.js` | `BASE_URL` / `https://www.example-portal.example` used to absolutise relative canonical links | if the live blob uses relative hrefs, set both to the real origin locally before a live run; keep the change out of commits |

## 3. Manual step — re-verify the parser against the live site (required)

The parser was rewritten in this build. Confirm it still matches the
predecessor's live result before treating any live number as delivered.

1. `pip install -e ".[dev]"` and install Node (`node --version` ≥ 18) so the
   parity test runs locally too.
2. Edit `extension/manifest.json` match patterns to the real portal origin
   (see the table above). Load `extension/` unpacked in Chrome
   (`extension/README.md`).
3. Browse the same suburb search used on 2026-08-30 (or the client's list).
   Click **Scan this page** on each results page. Do not automate.
4. **Export CSV.** Record: total rows, unique `listing_url`, agency cards (should
   be 0), dead links (should be 0).
5. Paste those into `README.md` and remove the `<<FILL>>` line. If they do not
   match 26 / 26 / 0 / 0 within the expected drift, open an issue before
   publishing.

## 4. Other manual steps

- **Node in CI:** `.github/workflows/ci.yml` already installs Node 20 so
  `tests/test_parity.py` executes on the runner. No action unless you change the
  workflow.
- **Playwright route, live:** needs an Australian residential proxy in
  `PROXY_URL` (see `.env.example`). Untested end to end — treat a first live run
  as exploratory. `listing-extract --suburb "..." --dry-run` first.
- **Demo GIF (optional):** `docs/RECORD_GIF.md`. Save as `docs/demo.gif`, add it
  under the hero image in `README.md`.
- **License holder:** `LICENSE` says "Manh" — change if you want your full name.
- **Screenshots:** `docs/extension_panel.png` and `docs/extension_popup.png` were
  produced this build against local fixtures. Re-take only if the panel/popup
  UI changes (`python scripts/serve_fixtures.py`, then screenshot).

## 5. Before pushing

```bash
pip install -e ".[dev]"
ruff format --check .
ruff check .
python scripts/check_no_pii.py
pytest                 # 51 tests; parity runs with Node, skips loudly without
```
