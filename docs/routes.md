# Two routes

Both routes use the **same parser** and produce the **same 17-field rows**. They
differ only in how the HTML is obtained.

## At a glance

| | Extension route | Playwright route |
|---|---|---|
| How pages load | a person browses normally | a headless browser navigates |
| Anti-bot | not triggered — a real browser driven by a person | triggered — needs an **AU residential proxy**; still stops itself after repeated blocks |
| Setup | load unpacked in Chrome, click "Grant access to this site" | `pip install -e ".[playwright]"`, `playwright install chromium`, set `PROXY_URL` |
| Cost | none | proxy cost (per GB or per IP) |
| Speed | one person, a few pages per minute | as fast as the proxy and delays allow |
| Good for | a suburb list a person can page through in a sitting | more volume than that |
| Proven | yes — predecessor prototype, live, 2026-08-30 (see README) | no — never completed end to end (429 from a non-AU IP) |
| Output | `Scan` per page → `Export CSV` / `Export XLSX` | `listing-extract --suburb ... --proxy ...` → `output/listings.csv` + `.xlsx` |

## When to use the extension route

- The job is a **one-time export** for a defined list of suburbs.
- A person is available to open each search page and click **Scan**.
- You do not want to pay for a proxy or manage one.

This is the route the predecessor prototype delivered with, and the one this
build is built around.

What it cannot do: run unattended, page through hundreds of result pages without
a person, or collect while nobody is at the keyboard.

## When to use the Playwright route

- The suburb list is too long to hand-page in a reasonable sitting.
- You have an **Australian residential proxy** (`PROXY_URL`), or a client who
  will supply one.

It builds `buy` / `rent` / `sold` search URLs per suburb, discovers the real page
count from `maxPageNumberAvailable`, waits a randomised delay between requests,
retries a blocked page with growing backoff, and **stops the whole run after N
consecutive blocked pages** (default 3), listing every blocked URL in the
summary.

What it cannot do: work without a proxy from most IPs (first request → 429/403),
solve a challenge, or guarantee completion — the predecessor never got this route
to finish against the live site.

Dry run (no browser, no proxy — just prints the URLs it would visit):

```
listing-extract --suburb "Richmond, VIC 3121" --channel buy --pages 5 --dry-run
```

## What both routes leave empty on purpose

- A listing with no canonical link → empty `listing_url` → the row is dropped
  with a reason (never a fabricated dead link).
- A project / "New Apartments" listing → range price, no single bed/bath count;
  `price_value` and the feature columns stay empty.
- A rural/acreage listing with the street address withheld → `address_full`
  empty, `suburb` / `state` / `postcode` kept.
