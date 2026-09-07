#!/usr/bin/env python3
"""Assert the built marketing site is indexable as distinct pages.

Run against ``site/out`` after ``npm run build``. Stdlib-only, like
``scripts/check_commercial_terms.py``.

Three rules, each of which had been broken in production before this existed:

1. **Every page canonicalizes to itself.** The root layout sets
   ``alternates: { canonical: '/' }`` and Next.js merges metadata shallowly on
   top-level keys, so any page that did not set its own ``alternates``
   inherited the homepage's. Six pages — ``/pricing/`` and ``/effectiveness/``
   among them — shipped ``rel=canonical`` pointing at ``/``, telling Google
   they were duplicates of the homepage while the sitemap submitted them at
   priority 0.8.

2. **Every page carries its own ``og:url`` and an ``og:image``.** The same
   shallow merge bites in the other direction: a page that *declares*
   ``openGraph`` replaces the root's block entirely, and all six
   ``/publications/*`` pages had silently lost ``og:image``.

3. **The sitemap lists exactly the pages that exist**, at the URLs they
   actually canonicalize to. The hand-maintained ``public/sitemap.xml`` had
   dropped ``/team/`` and listed ``/publications/*`` without the trailing
   slash the pages resolve to.

Exit 0 when clean, 1 with the offending pages named otherwise.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

SITE_URL = "https://neuralmind.uk"

CANONICAL_RE = re.compile(r'<link rel="canonical" href="([^"]+)"', re.I)
OG_URL_RE = re.compile(r'<meta property="og:url" content="([^"]+)"', re.I)
OG_IMAGE_RE = re.compile(r'<meta property="og:image" content="([^"]+)"', re.I)
LOC_RE = re.compile(r"<loc>([^<]+)</loc>", re.I)


def page_url(html_file: Path, out_dir: Path) -> str:
    """The absolute URL a built ``index.html`` is served at (trailingSlash: true)."""
    rel = html_file.relative_to(out_dir).parent.as_posix()
    return f"{SITE_URL}/" if rel == "." else f"{SITE_URL}/{rel}/"


def main(argv: list[str]) -> int:
    out_dir = Path(argv[1] if len(argv) > 1 else "site/out").resolve()
    if not out_dir.is_dir():
        print(f"error: no build output at {out_dir} — run `npm run build` in site/ first")
        return 1

    pages = sorted(
        f
        for f in out_dir.rglob("index.html")
        # 404 is intentionally not a canonical, indexable page.
        if "404" not in f.relative_to(out_dir).parts
    )
    if not pages:
        print(f"error: no pages found under {out_dir}")
        return 1

    failures: list[str] = []
    seen: set[str] = set()

    for page in pages:
        url = page_url(page, out_dir)
        seen.add(url)
        html = page.read_text(encoding="utf-8", errors="replace")

        canonical = CANONICAL_RE.search(html)
        if not canonical:
            failures.append(f"{url} — no rel=canonical")
        elif canonical.group(1) != url:
            failures.append(
                f"{url} — canonical points at {canonical.group(1)} "
                f"(a page must canonicalize to itself, or it asks to be dropped)"
            )

        og_url = OG_URL_RE.search(html)
        if not og_url:
            failures.append(f"{url} — no og:url")
        elif og_url.group(1) != url:
            failures.append(f"{url} — og:url is {og_url.group(1)}")

        if not OG_IMAGE_RE.search(html):
            failures.append(f"{url} — no og:image (a declared openGraph block replaces the root's)")

    sitemap = out_dir / "sitemap.xml"
    if not sitemap.is_file():
        failures.append("sitemap.xml missing from the export (app/sitemap.ts should generate it)")
    else:
        listed = set(LOC_RE.findall(sitemap.read_text(encoding="utf-8")))
        for url in sorted(seen - listed):
            failures.append(f"{url} — page exists but is not in sitemap.xml")
        for url in sorted(listed - seen):
            failures.append(f"{url} — in sitemap.xml but no such page was exported")

    if failures:
        print(f"site SEO check FAILED ({len(failures)} problem(s)):")
        for f in failures:
            print(f"  - {f}")
        return 1

    print(f"site SEO check passed: {len(pages)} page(s), each self-canonical and in the sitemap")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
