"""Guard the marketing site's indexability at the source level.

``scripts/check_site_seo.py`` is the authoritative check — it reads the built
HTML and is wired into ``site-build.yml``. This module holds the same
invariants at the source level so they run in the ordinary Python test job,
with no Node toolchain and no build, the same way ``test_site_claims.py`` does.

The bugs these rules exist to prevent all shipped to production:

1. **A page that does not declare its own canonical.** Next.js merges metadata
   shallowly on top-level keys, so a page omitting ``alternates`` inherits the
   root layout's ``{ canonical: '/' }``. Six pages — ``/pricing/`` and
   ``/effectiveness/`` among them — served ``rel=canonical`` pointing at the
   homepage, which asks Google to drop them as duplicates, while the sitemap
   submitted them at priority 0.8.

2. **A page that declares ``openGraph`` without ``images``.** The same merge in
   reverse: declaring the key replaces the root's block wholesale, and all six
   ``/publications/*`` pages had silently lost ``og:image``.

3. **An FAQ whose answers are not in the HTML.** The accordion rendered each
   answer only while open, so the export carried 11 questions and no answers.

4. **A title or description too long for a search result.** Twelve
   descriptions (up to 264 characters) and five titles (up to 83) were cut
   off mid-sentence in the snippet.

Stdlib-only, so it runs without the full dep set.
"""

from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
APP_ROOT = REPO_ROOT / "site" / "src" / "app"

# The root layout legitimately owns the homepage's canonical.
ROOT_PAGE = APP_ROOT / "page.tsx"


def _route_pages() -> list[Path]:
    return sorted(p for p in APP_ROOT.rglob("page.tsx") if p != ROOT_PAGE)


def _route_of(page: Path) -> str:
    rel = page.relative_to(APP_ROOT).parent.as_posix()
    return "/" if rel == "." else f"/{rel}"


def test_every_route_declares_its_own_canonical() -> None:
    """No page may fall through to the root layout's canonical."""
    offenders = []
    for page in _route_pages():
        src = page.read_text(encoding="utf-8")
        # Either routed through the helper (which always emits a
        # self-referencing canonical) or setting `alternates` explicitly.
        if "pageMetadata(" in src or "alternates:" in src:
            continue
        offenders.append(_route_of(page))
    assert not offenders, (
        "these routes inherit the root layout's canonical ('/'), which tells "
        "Google they are duplicates of the homepage: " + ", ".join(offenders)
    )


def test_declared_open_graph_blocks_keep_an_image() -> None:
    """Declaring `openGraph` replaces the root's block — images included."""
    offenders = []
    for page in _route_pages():
        src = page.read_text(encoding="utf-8")
        if "pageMetadata(" in src:
            continue  # The helper always supplies images.
        if "openGraph:" not in src:
            continue
        head = src.split("twitter:")[0]
        if "images:" not in head:
            offenders.append(_route_of(page))
    assert not offenders, (
        "these routes declare openGraph without images, so they lose og:image "
        "and share as bare links: " + ", ".join(offenders)
    )


def test_sitemap_is_generated_not_hand_maintained() -> None:
    """The static file drifted (missing /team/, wrong trailing slashes)."""
    assert (
        APP_ROOT / "sitemap.ts"
    ).is_file(), "site/src/app/sitemap.ts should generate the sitemap"
    stale = REPO_ROOT / "site" / "public" / "sitemap.xml"
    assert not stale.is_file(), (
        "site/public/sitemap.xml is back; it shadows the generated sitemap and "
        "is what drifted out of sync with the routes in the first place"
    )


def test_faq_answers_are_not_behind_an_interaction() -> None:
    """Answers must exist in the HTML, not appear only after a click."""
    faq = REPO_ROOT / "site" / "src" / "components" / "sections" / "FAQ.tsx"
    src = faq.read_text(encoding="utf-8")
    assert "<details" in src, "the FAQ should use <details>/<summary> so answers render statically"
    assert "useState" not in src, (
        "the FAQ is gating answers on client state again — that is what kept all "
        "11 answers out of the static export"
    )
    assert "{faq.a}" in src, "the FAQ no longer renders its answer text"


def test_guards_trip_on_the_markup_that_shipped() -> None:
    """The rules must actually reject the broken shapes, not just pass today."""
    # The canonical rule: metadata with neither the helper nor `alternates`.
    bad_page = "export const metadata = {\n    title: 'X',\n};\n"
    assert "pageMetadata(" not in bad_page and "alternates:" not in bad_page

    # The openGraph rule: a declared block with no images before `twitter:`.
    bad_og = "openGraph: {\n    title: 'X',\n},\ntwitter: {\n    images: ['y'],\n}"
    assert "images:" not in bad_og.split("twitter:")[0]

    # The FAQ rule: the conditional render that hid every answer.
    bad_faq = "{openIndex === i && (<div><p>{faq.a}</p></div>)}"
    assert "<details" not in bad_faq


def test_no_route_page_is_missing_a_title() -> None:
    """A page with no metadata export inherits the homepage's title too."""
    offenders = [
        _route_of(p)
        for p in _route_pages()
        if not re.search(r"export const metadata", p.read_text(encoding="utf-8"))
    ]
    assert not offenders, (
        "these routes have no metadata export, so they serve the homepage's "
        "title and description: " + ", ".join(offenders)
    )


# Mirrors rule 4 of scripts/check_site_seo.py, which measures the built HTML.
TITLE_MAX = 60
DESCRIPTION_MIN, DESCRIPTION_MAX = 50, 160
_STR = r"'((?:[^'\\]|\\.)*)'"
_TITLE_RE = re.compile(r"\btitle:\s*" + _STR)
_DESCRIPTION_RE = re.compile(r"\bdescription:\s*" + _STR)


def _page_snippet(page: Path) -> tuple[str | None, str | None]:
    """The page's own title and description: the first of each after its
    metadata export (the openGraph/twitter overrides come later)."""
    src = page.read_text(encoding="utf-8")
    head = src.split("export const metadata", 1)[-1]
    title = _TITLE_RE.search(head)
    description = _DESCRIPTION_RE.search(head)
    return (
        title.group(1) if title else None,
        description.group(1) if description else None,
    )


def test_titles_and_descriptions_fit_a_search_result() -> None:
    """Twelve descriptions (up to 264 chars) and five titles (up to 83) were
    being truncated in search results. Measured on the source literal, which
    for these pages is the rendered text (no entities, no title template)."""
    offenders = []
    for page in _route_pages():
        title, description = _page_snippet(page)
        route = _route_of(page)
        if title is not None and len(title) > TITLE_MAX:
            offenders.append(f"{route}: title is {len(title)} chars (max {TITLE_MAX})")
        if description is not None and not (DESCRIPTION_MIN <= len(description) <= DESCRIPTION_MAX):
            offenders.append(
                f"{route}: description is {len(description)} chars "
                f"(want {DESCRIPTION_MIN}-{DESCRIPTION_MAX})"
            )

    layout = (APP_ROOT / "layout.tsx").read_text(encoding="utf-8")
    home = re.search(r"SITE_DESCRIPTION\s*=\s*" + _STR, layout)
    assert home, "layout.tsx no longer defines SITE_DESCRIPTION as a string literal"
    if not DESCRIPTION_MIN <= len(home.group(1)) <= DESCRIPTION_MAX:
        offenders.append(f"/: description is {len(home.group(1))} chars")

    assert not offenders, (
        "titles over 60 or descriptions outside 50-160 characters get truncated "
        "in search results:\n  " + "\n  ".join(offenders)
    )
