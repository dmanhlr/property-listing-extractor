"""Serve the synthetic fixture pages on localhost.

    python scripts/serve_fixtures.py [--port 8000]

Used for taking extension screenshots against local pages (never the live site)
and for a quick manual look at what the parser sees. An index at ``/`` links the
pages.
"""

from __future__ import annotations

import argparse
import http.server
import socketserver
from functools import partial
from pathlib import Path

PAGES_DIR = Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "pages"


class Handler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self) -> None:  # noqa: N802 (stdlib name)
        if self.path in ("/", "/index.html"):
            body = self._index().encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        super().do_GET()

    def _index(self) -> str:
        links = "\n".join(
            f'<li><a href="/{p.name}">{p.name}</a></li>'
            for p in sorted(PAGES_DIR.glob("*.html"))
        )
        return (
            "<!doctype html><meta charset='utf-8'><title>fixture pages</title>"
            "<h1>Fixture pages (synthetic)</h1><ul>" + links + "</ul>"
        )

    def log_message(self, *args) -> None:  # keep the console quiet
        pass


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()

    handler = partial(Handler, directory=str(PAGES_DIR))
    with socketserver.TCPServer(("127.0.0.1", args.port), handler) as httpd:
        print(f"serving {PAGES_DIR} at http://127.0.0.1:{args.port}/  (Ctrl+C to stop)")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nstopped")


if __name__ == "__main__":
    main()
