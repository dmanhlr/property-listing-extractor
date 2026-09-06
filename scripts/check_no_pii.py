"""Fail if tracked text files contain personal data.

Scans for:
  * email addresses (outside an allowlist of ``*.example`` and known no-reply
    addresses),
  * phone-number-looking strings,
  * street-address-looking strings, everywhere except the synthetic fixtures and
    the generator that writes them.

Runs in CI. Exit code 1 on the first finding.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

TEXT_SUFFIXES = {
    ".py",
    ".js",
    ".md",
    ".json",
    ".toml",
    ".yml",
    ".yaml",
    ".txt",
    ".css",
    ".html",
    ".cfg",
    ".ini",
    ".env",
    ".example",
}

# Paths (relative, posix) skipped entirely: third-party bundled code.
FULL_SKIP = (
    "extension/vendor/",
    "scripts/check_no_pii.py",  # this file names the patterns it looks for
)

# Paths excluded from the street-address heuristic only: the fixtures are
# deliberately address-shaped, and so is the script that builds them.
ADDRESS_SCAN_SKIP = (
    "tests/fixtures/",
    "tests/",
    "scripts/generate_fixtures.py",
)

EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
EMAIL_ALLOW = re.compile(
    r"@([A-Za-z0-9-]+\.)?example(\.[A-Za-z]{2,})?$"
    r"|@example\.(com|org|net)$"
    r"|^noreply@anthropic\.com$"
    r"|^noreply@github\.com$"
    r"|^\d+\+[\w-]+@users\.noreply\.github\.com$"
)

PHONE_RE = re.compile(r"(?<!\d)(?:\+?61[ -]?|\(0\d\)[ -]?|0)(?:\d[ -]?){8,9}\d(?!\d)")

STREET_RE = re.compile(
    r"\b\d{1,4}[A-Za-z]?\s+(?:[A-Z][a-z]+\s){1,3}"
    r"(?:Street|St|Road|Rd|Avenue|Ave|Lane|Ln|Court|Ct|Drive|Dr|Place|Pl|"
    r"Terrace|Tce|Parade|Pde|Crescent|Cres|Close|Cl|Way|Boulevard|Blvd|"
    r"Highway|Hwy|Circuit|Cct|Grove|Gr)\b"
)


def tracked_files() -> list[Path]:
    try:
        out = subprocess.run(
            ["git", "ls-files"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            check=True,
        ).stdout
        files = [REPO_ROOT / line for line in out.splitlines() if line.strip()]
        if files:
            return files
    except (subprocess.CalledProcessError, FileNotFoundError):
        pass
    # Fallback: walk, skipping the obvious noise.
    skip = {".git", "venv", ".venv", "node_modules", "output", "__pycache__"}
    result = []
    for path in REPO_ROOT.rglob("*"):
        if path.is_file() and not (skip & set(path.relative_to(REPO_ROOT).parts)):
            result.append(path)
    return result


def _rel(path: Path) -> str:
    return path.relative_to(REPO_ROOT).as_posix()


def scan() -> list[str]:
    findings: list[str] = []
    for path in tracked_files():
        if path.suffix.lower() not in TEXT_SUFFIXES and path.name != ".env.example":
            continue
        rel = _rel(path)
        if any(rel.startswith(p) or rel == p for p in FULL_SKIP):
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue

        for lineno, line in enumerate(text.splitlines(), start=1):
            for match in EMAIL_RE.finditer(line):
                if not EMAIL_ALLOW.search(match.group(0)):
                    findings.append(f"{rel}:{lineno}: email-like: {match.group(0)}")
            for match in PHONE_RE.finditer(line):
                digits = re.sub(r"\D", "", match.group(0))
                if len(digits) >= 9:
                    findings.append(
                        f"{rel}:{lineno}: phone-like: {match.group(0).strip()}"
                    )
            if not any(rel.startswith(p) for p in ADDRESS_SCAN_SKIP):
                for match in STREET_RE.finditer(line):
                    findings.append(f"{rel}:{lineno}: address-like: {match.group(0)}")
    return findings


def main() -> int:
    findings = scan()
    if findings:
        print("check_no_pii: FAIL")
        for f in findings:
            print(f"  {f}")
        return 1
    print("check_no_pii: OK (no email / phone / street-address patterns found)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
