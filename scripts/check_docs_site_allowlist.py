#!/usr/bin/env python3
"""Gate: docs/ holds only files that belong on the public docs site.

GitHub Pages builds https://docs.neuralmind.uk/ from main:/docs (legacy Jekyll
build; the domain is in docs/CNAME). It publishes on every push to main and
does not wait for CI, so a file committed under docs/ is public within
minutes, whether or not it is documentation.

On 2026-10-02 two model-training scripts from another project were pushed
straight to main under docs/ (c8c6b8f), and both could be downloaded from
docs.neuralmind.uk. The only signal was the Lint job failing on their
formatting. It stayed red through four pushes and a release, because "black
would reformat" says nothing about a file being public.

So this check fails on any tracked file under docs/ whose type is not on the
allowlist, and says why that matters. The allowlist is what the site holds
(git ls-files docs/ on 2026-10-03) plus the other common image formats.
Adding a type should be a deliberate choice, made in the same change where
review can see it.

It checks file types, not content: a private note saved as .md still passes.

Exit 0 = clean. Exit 1 = files that don't belong, one line per path.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parent.parent
# Pages' custom domain, from docs/CNAME. tests/test_docs_site_allowlist.py
# keeps the two in step.
SITE_URL = "https://docs.neuralmind.uk/"

ALLOWED_SUFFIXES = {
    # Pages: markdown that Jekyll renders (wiki, use cases, release notes, ...)
    # and static HTML.
    ".md",
    ".html",
    # Assets for the HTML pages.
    ".css",
    ".js",
    # Images. Only .png is in use; the rest are the other formats a page might link.
    ".png",
    ".svg",
    ".jpg",
    ".jpeg",
    ".gif",
    ".webp",
    ".ico",
    # Files the site serves on purpose (sitemap.xml, robots.txt, llms.txt, the
    # community-benchmarks feed and its schema, the golden-queries template),
    # plus Jekyll's _config.yml.
    ".json",
    ".txt",
    ".xml",
    ".yml",
}
# Pages reads the custom domain from CNAME; .gitkeep keeps docs/images/ in git.
ALLOWED_NAMES = {"CNAME", ".gitkeep"}


def tracked_docs_files() -> list[str]:
    out = subprocess.run(
        ["git", "ls-files", "-z", "--", "docs/"],
        cwd=ROOT,
        capture_output=True,
        encoding="utf-8",
        check=True,
    ).stdout
    return [f for f in out.split("\0") if f]


def is_allowed(path: str) -> bool:
    p = PurePosixPath(path)
    return p.name in ALLOWED_NAMES or p.suffix.lower() in ALLOWED_SUFFIXES


def disallowed(paths: list[str]) -> list[str]:
    return [p for p in paths if not is_allowed(p)]


def failure_message(paths: list[str]) -> str:
    listing = "\n".join(f"  - {p}" for p in paths)
    return (
        f"docs/ allowlist check FAILED ({len(paths)} file(s) that are not docs-site types):\n"
        f"{listing}\n\n"
        f"docs/ is published at {SITE_URL}. GitHub Pages serves it straight from "
        "main without waiting for CI, so a file committed here goes public within "
        "minutes. Move anything that is not part of the docs site out of docs/. If "
        "it is part of the site, add its type to ALLOWED_SUFFIXES in "
        "scripts/check_docs_site_allowlist.py in the same change."
    )


def main() -> int:
    files = tracked_docs_files()
    bad = disallowed(files)
    if bad:
        print(failure_message(bad))
        return 1
    print(
        f"docs/ allowlist check passed: all {len(files)} files under docs/ are "
        f"docs-site types (published at {SITE_URL})"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
