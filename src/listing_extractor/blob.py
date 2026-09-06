"""Find the embedded assignment, scan one balanced object, un-stringify it.

The portal server-renders its data into a ``<script>`` that assigns
``window.ArgonautExchange = {...}``. Inside, values are JSON strings stringified
one or more levels deep (a urql GraphQL client cache). The page wipes the live
``window.ArgonautExchange`` variable after hydration, so a reader must take the
*text* of the script tag, not the variable.

Approach that survives markup changes: find the assignment, scan one balanced
``{...}`` with a string-aware brace counter, then walk the object recursively,
parsing any string that looks like JSON, and collect every dict that looks like
a listing. Key paths are never hard-coded -- they change.
"""

from __future__ import annotations

import json
import re
from collections.abc import Iterator
from typing import Any

_ASSIGN_RE = re.compile(r"window\.ArgonautExchange\s*=\s*")
_SCRIPT_RE = re.compile(r"<script\b[^>]*>(.*?)</script>", re.IGNORECASE | re.DOTALL)

# Depth guard for find_max_page: the cache nests a handful of levels; 60 is far
# past that and still stops runaway recursion on a pathological blob.
_MAX_DEPTH = 60


def _scan_balanced(s: str, i: int) -> tuple[Any, int]:
    """Parse one balanced ``{...}`` / ``[...]`` at or after index ``i``.

    Skips leading whitespace. Counts braces while respecting string literals and
    backslash escapes, so a ``}`` inside a quoted value does not end the scan.
    Returns ``(parsed_value, index_just_past_it)``.
    """
    n = len(s)
    while i < n and s[i] in " \t\r\n":
        i += 1
    if i >= n or s[i] not in "{[":
        raise ValueError("no JSON object at the assignment")
    start = i
    depth = 0
    in_str = False
    esc = False
    while i < n:
        c = s[i]
        if in_str:
            if esc:
                esc = False
            elif c == "\\":
                esc = True
            elif c == '"':
                in_str = False
        else:
            if c == '"':
                in_str = True
            elif c in "{[":
                depth += 1
            elif c in "}]":
                depth -= 1
                if depth == 0:
                    return json.loads(s[start : i + 1]), i + 1
        i += 1
    raise ValueError("unterminated JSON object")


def _iter_script_texts(html: str) -> Iterator[str]:
    """Yield the text content of every ``<script>`` in ``html``.

    If nothing parses as a script tag (a bare fragment), yield the whole string
    so callers still work on raw blob text.
    """
    found = False
    for m in _SCRIPT_RE.finditer(html):
        found = True
        yield m.group(1)
    if not found:
        yield html


def extract_blob(html: str) -> Any:
    """Return the parsed ``ArgonautExchange`` object, or ``{}`` if absent.

    Reads the script tag's text (never a live JS variable). Tolerant: a script
    whose assignment does not scan cleanly is skipped, not raised on.
    """
    for text in _iter_script_texts(html):
        m = _ASSIGN_RE.search(text)
        if not m:
            continue
        try:
            obj, _ = _scan_balanced(text, m.end())
            return obj
        except ValueError:
            continue
    return {}


def _maybe_json(value: Any) -> Any:
    """If ``value`` is a str that parses as JSON, return the parsed value."""
    if isinstance(value, str):
        t = value.lstrip()
        if t[:1] in "{[":
            try:
                return json.loads(value)
            except (ValueError, TypeError):
                return value
    return value


def iter_listings(node: Any, _seen: set[str] | None = None) -> Iterator[dict]:
    """Yield every listing-shaped dict anywhere inside ``node``.

    Recurses through dicts and lists, un-stringifying JSON strings on the way.
    De-dupes within one call by listing id so the same object reached by two
    cache keys is yielded once. ``shape.looks_like_listing`` decides what counts.
    """
    from listing_extractor.shape import listing_key, looks_like_listing

    if _seen is None:
        _seen = set()
    node = _maybe_json(node)
    if isinstance(node, dict):
        if looks_like_listing(node):
            key = listing_key(node)
            if key not in _seen:
                _seen.add(key)
                yield node
        for v in node.values():
            yield from iter_listings(v, _seen)
    elif isinstance(node, list):
        for v in node:
            yield from iter_listings(v, _seen)


def find_max_page(node: Any, _depth: int = 0) -> int | None:
    """Locate the max-page value in the blob (depth-limited).

    Search pages carry a ``maxPageNumberAvailable`` (or similar) somewhere in
    the nested cache. Returns the first positive integer found under one of the
    known key names, or ``None``.
    """
    if _depth > _MAX_DEPTH:
        return None
    node = _maybe_json(node)
    if isinstance(node, dict):
        for k in ("maxPageNumberAvailable", "maxPageNumber", "totalPages"):
            v = node.get(k)
            if isinstance(v, int) and not isinstance(v, bool) and v > 0:
                return v
        for v in node.values():
            r = find_max_page(v, _depth + 1)
            if r:
                return r
    elif isinstance(node, list):
        for v in node:
            r = find_max_page(v, _depth + 1)
            if r:
                return r
    return None
