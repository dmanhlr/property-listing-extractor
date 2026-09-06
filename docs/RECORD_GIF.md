# Recording the demo GIF

A short GIF of the extension route, taken against the local fixture pages (never
the live site). Optional — the README works without it.

## Setup

```
pip install -e ".[dev,playwright]"
playwright install chromium
python scripts/generate_fixtures.py        # if not already generated
python scripts/serve_fixtures.py --port 8000
```

Load `extension/` unpacked in Chrome (see `extension/README.md`). Leave the match
patterns on `localhost` for this recording.

## What to record (~15 s)

1. Open `http://127.0.0.1:8000/search-buy-riverbend-1.html`.
2. The **Listing Collector** panel appears. Click **Scan this page** —
   counts jump to 24 on page, 23 unique, 1 skipped (no link).
3. Open `http://127.0.0.1:8000/search-buy-riverbend-2.html`, click
   **Scan this page** — unique goes to 26, duplicates skipped 1.
4. Click **Export CSV**. Show the downloaded file.

## Capture

- **Windows:** ScreenToGif (<https://www.screentogif.com/>), region = the browser
  window, 15 fps, then Save as GIF.
- **macOS/Linux:** `peek` or `byzanz-record`, or record `.mov` / `.mp4` and
  convert:
  ```
  ffmpeg -i demo.mp4 -vf "fps=15,scale=900:-1:flags=lanczos" -loop 0 docs/demo.gif
  ```

## Place it

Save as `docs/demo.gif`. Add under the hero image in `README.md`:

```markdown
![demo](docs/demo.gif)
```

Keep it under ~4 MB so it renders inline on GitHub.
