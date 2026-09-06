# property-listing-extractor

Clean listing data out of a bot-protected property portal, two ways: a Chrome extension
that collects listings while a person browses normally, and a Playwright route for
volume that needs an Australian residential proxy. One parser, two runtimes, tested to
agree.

This is a **public portfolio repo**. Its readers are Upwork clients (non-technical,
30 seconds — the README image and the numbers) and technical reviewers (5 minutes —
they run the demo and look at the parity test). Optimize for the first, then the second.

## Status

Mark `[x]` with a date and a one-line note as each phase completes.

- [x] Phase 1 — 2026-09-06 — blob/shape/mapping/validate/export/cli, src layout, ruff+CI, 51 tests.
- [x] Phase 2 — 2026-09-06 — `scripts/generate_fixtures.py` → 2 search pages + 1 detail page, all six regressions reproduced; fixtures README maps each.
- [x] Phase 3 — 2026-09-06 — MV3 extension, one shared `parser.js`, `tests/test_parity.py` (Python vs `node parser.js`, row-for-row; skips loudly without Node).
- [x] Phase 4 — 2026-09-06 — `routes/playwright_route.py`, mocked-fetcher unit test, `--dry-run`, stop-after-N-blocks, `PROXY_URL`.
- [x] Phase 5 — 2026-09-06 — `listing-extract --demo` (28→26), `docs/output_preview.png`, `docs/extension_panel.png` + `extension_popup.png` (Playwright + unpacked extension vs local fixtures).
- [x] Phase 6 — 2026-09-06 — README (layout + labelled numbers), `docs/routes.md`, `docs/RECORD_GIF.md`, `PUBLISH.md`, `check_no_pii.py`.

## This is a new build

Reference material, read but never copy:
- `D:\Code\Web_NoJD` — `rea_scraper/argonaut.py` (blob extraction), `mapping.py` (field
  mapping, price parsing), `browser.py` (Playwright route), `tests/test_offline.py`
  (regression cases), `extension-test/` (extension v0.3, `shared.js` holds the JS port),
  `README.md` and `CLAUDE.md` (feasibility findings and the live-test log).
- `D:\Code\PyApp\chrome-extension\content\` — borrow three patterns only, nothing about
  that site or its data: `panel.js` (draggable in-page panel with status, progress and
  buttons), `sessionState.js` (per-tab state in `sessionStorage` that survives full-page
  navigations), `excelExport.js` (SheetJS bundled offline and the download issued from
  the background worker, because Manifest V3's CSP forbids loading a CDN script).

There are **no saved real pages** in the reference folder, and no real listing data may
enter this repo anyway. Fixtures are therefore synthetic but structurally faithful:
they reproduce the real blob's shape and the six regression cases below, using
`*.example` domains and Faker names.

## What the reference material establishes

The site is an Australian property portal protected by Kasada (TLS fingerprinting, JS
challenge, geo filter, rate limits). Plain HTTP clients and headless browsers get
429/403 on the first request from non-AU IPs.

The data is server-rendered into a `<script>` that assigns `window.ArgonautExchange = {…}`.
Inside, values are JSON strings stringified one or more levels deep (a urql GraphQL
cache). Listing objects carry `address{suburb,state,postcode,…}`, `price{display}`,
`propertyType`, `generalFeatures{bedrooms,bathrooms,parkingSpaces}`, `listers[]`,
`media{images[templatedUrl]}`, `_links{canonical}`; search pages carry
`maxPageNumberAvailable`. **The page wipes the live `window.ArgonautExchange` variable
after hydration**, so an extension must read the script tag's text, not the variable.

Parsing approach that works: find the assignment, scan one balanced `{…}` with a
string-aware brace counter, then walk the object recursively, parsing any string that
looks like JSON, and collect every dict that looks like a listing. Do not hard-code key
paths — they change.

Six regression cases found on live data. Each must be a test here, reproduced
structurally in a fixture:
1. Agency cards leaked in (23 of 53 rows) because the shape test accepted any object
   with `address` + `media`. Require `address.suburb`; drop `media` from the test.
2. Listings without `_links.canonical` were given a fabricated URL that was dead. Leave
   `listing_url` empty and let validation drop the row.
3. "Project" listings (`New Apartments`) price per unit as a range and carry no single
   beds/baths — map what exists, leave the rest empty, set `listing_kind = project`.
4. Rural/acreage listings hide the street address deliberately; suburb/state/postcode
   are still present — keep the row with `address_full` empty.
5. Price text variants: `Contact agent`, `Offers over $900k`, `$1,250,000`,
   `$800,000 - $850,000` (a range leaves `price_value` empty), `k`/`m` suffixes.
6. Templated image URLs contain `{size}`; expand to a fixed size, never ship `{…}`.

Live results from the predecessor prototype, to be quoted as such: extension route,
manual browsing, 2026-08-30 — first pass 53 rows revealing bugs 1 and 2; after fixes
26 rows, 26 unique URLs, 0 agency cards, 0 dead links. The Playwright route never
completed end to end (429 from a non-AU IP).

Field schema: `listing_url, address_full, suburb, state, postcode, price_text,
price_value, property_type, bedrooms, bathrooms, car_spaces, land_size, description,
agent_name, agency_name, listing_date, image_urls`. A row is valid when
`listing_url, suburb, state, postcode, price_text, property_type` are all present.

## Lessons carried from the sibling repos

Built before this one: `exhibitor-leadgen-pipeline`, `pdf-data-extractor`,
`llm-bulk-classifier`.

- One denominator per table, stated in the caption. Never mix numbers from different
  runs into one table without a provenance line.
- Label clearly what was measured live, what came from a predecessor prototype, and
  what is only fixture-verified. A reader must never have to guess which.
- Never guess silently: a field the source does not expose stays empty, and a row that
  fails validation is dropped with a reason, not repaired.
- Anything not produced in-session is `<<FILL: exact command>>`, listed in the final
  report.

## Design

```
src/listing_extractor/
  blob.py       find the assignment, balanced scan, recursive un-stringify,
                iter_listings, find_max_page (depth-limited)
  shape.py      looks_like_listing (address.suburb required), listing_kind detection
  mapping.py    raw dict -> Listing dataclass; price parsing; image URL expansion;
                agents; land size
  validate.py   required fields, dedupe by listing_url, drop log with reasons
  export.py     CSV (image_urls ';'-joined) + XLSX
  routes/playwright_route.py
                search URL builder per channel (buy | rent | sold), pagination via the
                max-page value, randomised delay, retry/backoff on 429/403, stop after
                N consecutive blocks, proxy from PROXY_URL, blocked URLs in the summary
  cli.py        listing-extract --demo | --suburb "Richmond, VIC 3121"
                [--channel buy] [--pages N] [--proxy URL] [--keep-agent] [--out DIR]
extension/      Manifest V3. parser.js is the single JS parser, used by both the
                content script and the popup (via chrome.scripting.executeScript).
                In-page panel: listings on this page, total collected, unique,
                duplicates skipped, last status; buttons Scan / Export CSV /
                Export XLSX / Clear. State in chrome.storage.local. XLSX via bundled
                SheetJS through the background worker. No auto-navigation, no
                background crawling — the person drives.
tests/          test_blob, test_shape, test_mapping, test_validate,
                test_playwright_route (mocked), test_parity, test_demo
tests/fixtures/pages/   synthetic search + detail pages (see below)
scripts/        render_preview.py, check_no_pii.py, serve_fixtures.py
docs/           routes.md, extension_panel.png, extension_popup.png,
                output_preview.png, RECORD_GIF.md
```

**Parity is the repo's technical centrepiece.** `tests/test_parity.py` loads each
fixture page, runs the Python parser, runs the JS parser under Node
(`node extension/parser.js <file>`), and asserts the two row sets are identical. If
Node is unavailable the test skips with a clear message rather than passing silently.

## Personal data and wording

- No real listing rows anywhere: not in fixtures, tests, screenshots, or docs.
- Real-estate agents are individuals: `agent_name` and `agency_name` are dropped unless
  `--keep-agent` is passed, and fixtures use Faker names on `*.example` domains.
- Screenshots are taken against fixture pages served locally by
  `scripts/serve_fixtures.py`, never against the live site.
- Never use the word "bypass". The wording is: *reads the page's own embedded JSON while
  a person browses*.
- The portal's brand name appears once, in the README's context line. Not in the repo
  name, the package name, the extension name, or the topics.
- `scripts/check_no_pii.py` scans tracked text files for email/phone patterns and for
  street-address-looking strings outside the fixtures; it runs in CI.

## Standards

**Language.** Code, comments, docstrings, README, sheet labels, commits: English. Short
sentences, numbers over adjectives. No "powerful", "seamless", "robust".

**README layout, in order.** (1) `# property-listing-extractor` + one line what/for whom.
(2) Hero image `docs/output_preview.png` — the exported sheet, <= 15 rows. (3) `## Results`
— fixture-verified parity and validation numbers from this build, then the predecessor
live numbers clearly labelled as such, then the Playwright route's status.
(4) `## The job this solves` — one-time export of every active listing for a list of
suburbs into one CSV the client imports by hand; no automation, no sync. (5) `## How it
works`. (6) `## Quick start` — demo in <= 3 commands, offline. (7) `## Two routes` —
point at `docs/routes.md`. (8) `## Data & privacy`. (9) `## Limitations` — 3-5 honest
bullets. (10) `## Stack`, `## License` (MIT).

**Demo mode is mandatory.** `listing-extract --demo` parses the bundled fixtures offline
and writes `output/listings.csv` + `.xlsx` with a summary (pages, rows seen, valid rows,
dropped with reasons).

**Code quality.** Python 3.10+, `src/` layout, `pyproject.toml` with pinned deps and a
`[dev]` extra. `ruff format` + `ruff check` clean. Type hints on public functions.
`logging`, not `print`, except the final summary. GitHub Actions `ci.yml` runs ruff,
pytest and `check_no_pii.py`, with Node available so the parity test really runs there.
`.env.example` documents `PROXY_URL`.

**Working style.** Build the whole project in one run, phase by phase in the Status
order, testing as you go; do not stop between phases for approval. Note assumptions.
Ask at most one question, in the final report. Do not push to GitHub — commit locally
and write `PUBLISH.md` with the `gh repo create` command, description, topics, every
`<<FILL>>`, and the manual steps left for Manh.

## Definition of done

- [ ] README follows the layout; hero image present; every number labelled by origin
      (this build / predecessor prototype / not run)
- [ ] `listing-extract --demo` works offline from a fresh clone
- [ ] `pytest` and `ruff check` pass; the parity test runs (or skips loudly)
- [ ] `check_no_pii.py` passes; no real listing data anywhere
- [ ] `extension/README.md` with load-unpacked steps; both screenshots present
- [ ] `docs/routes.md` explains when to use which route
- [ ] `.env.example`, `.gitignore`, `LICENSE`, `PUBLISH.md`, `docs/RECORD_GIF.md`
- [ ] Final report lists every `<<FILL>>` and every manual step
