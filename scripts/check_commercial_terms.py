#!/usr/bin/env python3
"""Gate: every surface agrees with commercial-terms.json.

Two checks, both driven by the JSON so policy changes never require
editing this script:

1. superseded_terms.patterns must appear NOWHERE in current surfaces
   (docs/releases/ and CHANGELOG.md are exempt as historical record).
2. required[].file must contain every string in required[].contains.

Exit 0 = aligned. Exit 1 = drift, with a per-hit report.
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TERMS = ROOT / "commercial-terms.json"

SCAN_SUFFIXES = {".md", ".tsx", ".ts", ".py", ".html", ".toml", ".json", ".yaml", ".yml"}
EXEMPT_PREFIXES = (
    "docs/releases/",
    "site/.next/",
    "site/out/",
    ".neuralmind",
)
EXEMPT_FILES = {
    "CHANGELOG.md",
    "commercial-terms.json",
    "scripts/check_commercial_terms.py",
}


def tracked_files() -> list[str]:
    out = subprocess.run(
        ["git", "ls-files"], cwd=ROOT, capture_output=True, text=True, check=True
    ).stdout
    return [
        f
        for f in out.splitlines()
        if Path(f).suffix in SCAN_SUFFIXES
        and not f.startswith(EXEMPT_PREFIXES)
        and f not in EXEMPT_FILES
    ]


def main() -> int:
    terms = json.loads(TERMS.read_text(encoding="utf-8"))
    patterns = [re.compile(p) for p in terms["superseded_terms"]["patterns"]]
    failures: list[str] = []

    for rel in tracked_files():
        try:
            text = (ROOT / rel).read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for lineno, line in enumerate(text.splitlines(), 1):
            for pat in patterns:
                if pat.search(line):
                    failures.append(
                        f"SUPERSEDED TERM {pat.pattern!r} at {rel}:{lineno}: {line.strip()[:120]}"
                    )

    for req in terms["required"]:
        path = ROOT / req["file"]
        if not path.exists():
            failures.append(f"REQUIRED FILE MISSING: {req['file']}")
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        for needle in req["contains"]:
            if needle not in text:
                failures.append(f"MISSING {needle!r} in {req['file']}")

    if failures:
        print(f"commercial-terms check FAILED ({len(failures)} hit(s)):")
        for f in failures:
            print(f"  - {f}")
        print("\nCanonical facts live in commercial-terms.json — align the surface "
              "(or, if the terms genuinely changed, update the JSON first).")
        return 1
    print("commercial-terms check passed: all surfaces agree with commercial-terms.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
