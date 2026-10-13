"""Guard docs.neuralmind.uk's indexability at the source level.

GitHub Pages builds the docs site from ``docs/`` with no CI step of ours in
between, so these invariants are held here, on the Jekyll sources. The
marketing site's equivalent is ``tests/test_site_seo.py``.

Each rule is a bug that shipped:

1. **One meta description for every page.** The layout fell back to
   ``site.description``, and wiki pages, use cases and release notes carry no
   front matter (it would show as text in the GitHub Wiki mirror), so 112 of
   122 pages served the same description.

2. **"NeuralMind Docs" as the title of the two most important pages.**
   ``wiki/Home.md`` and ``wiki/CLI-Reference.md`` open with an HTML comment,
   so jekyll-titles-from-headings finds no heading and the layout's generic
   title won. A page that doesn't start with a heading needs a title in
   ``_config.yml`` defaults.

3. **No ``og:url`` or ``twitter:card``** on any Markdown page.

Stdlib-only, so it runs without the full dep set.
"""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
DOCS = REPO_ROOT / "docs"
LAYOUT = DOCS / "_layouts" / "default.html"
CONFIG = DOCS / "_config.yml"


def _layout_head() -> str:
    src = LAYOUT.read_text(encoding="utf-8")
    return src[: src.index("</head>")]


def test_description_falls_back_to_the_page_not_the_site() -> None:
    head = _layout_head()
    assert "content | strip_html" in head, (
        "the layout no longer derives a description from the page's own text; "
        "every page without front matter would share site.description again"
    )
    assert "default: site.description" not in head, (
        "site.description is the direct fallback again — that is what gave "
        "112 of 122 pages one shared description"
    )


def test_layout_emits_social_and_robots_tags() -> None:
    head = _layout_head()
    for tag in ('property="og:url"', 'property="og:site_name"', 'name="twitter:card"'):
        assert tag in head, f"the docs layout lost {tag}"
    assert "page.noindex" in head, "the layout no longer honours a page's noindex"


def test_pages_without_a_leading_heading_are_titled_in_config() -> None:
    config = CONFIG.read_text(encoding="utf-8")
    offenders = []
    for md in sorted(DOCS.rglob("*.md")):
        rel = md.relative_to(DOCS).as_posix()
        if rel.startswith(("_", "vendor/")):
            continue
        first = next(
            (line for line in md.read_text(encoding="utf-8").splitlines() if line.strip()),
            "",
        )
        if first.startswith(("# ", "---")):
            continue  # titled by its heading or by its own front matter
        if f'path: "{rel}"' not in config:
            offenders.append(rel)
    assert not offenders, (
        "these pages don't open with a '# ' heading, so they render titled "
        "'NeuralMind Docs'; give each a title in docs/_config.yml defaults: " + ", ".join(offenders)
    )


def test_guards_trip_on_the_markup_that_shipped() -> None:
    """The rules must reject the broken shapes, not just pass today."""
    shipped = (
        '<meta name="description" content="{{ page.description | default: '
        'site.description | strip_newlines | escape }}">'
    )
    assert "default: site.description" in shipped
    assert "content | strip_html" not in shipped
    assert 'property="og:url"' not in shipped
