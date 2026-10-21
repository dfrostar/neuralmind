"""Guard the marketing site's design tokens.

A 2026-10 audit of ``site/src`` found the tokens in ``site/tailwind.config.ts``
covered surfaces and accents but nothing else: 112 arbitrary ``text-[…]`` /
``tracking-[…]`` values, 336 uses of Tailwind's slate scale for body text,
raw red/yellow/green for verdicts, eight border radii, and one class
(``text-electric-branch``) that named a colour nobody defined, so it rendered
in the inherited colour without anyone noticing.

The config now names every step (see ``site/DESIGN.md``). This module keeps it
that way:

1. **No arbitrary type values** — ``text-[…]``, ``leading-[…]``,
   ``tracking-[…]`` and ``font-[…]`` are banned; add a named step to the
   config's ``fontSize`` / ``lineHeight`` / ``letterSpacing`` instead.
   Arbitrary *layout* values (``w-[…]``, ``grid-cols-[…]``) are fine.
2. **No raw palette colours** — Tailwind's own scales (``slate-300``,
   ``red-400``, …) and arbitrary hex colours stay out of class names. Text is
   ``ink`` / ``body`` / ``muted`` / ``faint``; verdicts are ``danger`` /
   ``warn`` / ``success``; measured results are ``proton``.
3. **Three radii** — ``rounded-control``, ``rounded-card``, ``rounded-pill``
   (and ``rounded-none``). The config replaces Tailwind's radius scale, so any
   other ``rounded-*`` class silently generates nothing; this catches it.
4. **Every token class names a real token** — a colour utility that uses one
   of the site's palette names must name a colour the config defines.
5. **DESIGN.md lists every token** — the doc and the config change together.

Stdlib-only, like the claims guards, so it runs without the full dep set.
"""

from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SITE = REPO_ROOT / "site"
SRC = SITE / "src"
CONFIG = SITE / "tailwind.config.ts"
DESIGN_DOC = SITE / "DESIGN.md"

# A class token starts after whitespace, a quote, a backtick or `{`; variant
# prefixes (`md:`, `hover:`, `group-hover:`) are part of the token.
_START = r"(?<![\w\-\[])(?:[\w\-]+:)*"

ARBITRARY_TYPE = re.compile(_START + r"(?:text|leading|tracking|font)-\[[^\]]*\]")

TAILWIND_SCALES = (
    "slate|gray|zinc|neutral|stone|red|orange|amber|yellow|lime|green|emerald|"
    "teal|cyan|sky|blue|indigo|violet|purple|fuchsia|pink|rose"
)
COLOUR_UTILITIES = (
    "text|bg|border|ring|ring-offset|from|via|to|fill|stroke|divide|outline|"
    "decoration|shadow|placeholder|accent|caret"
)
RAW_PALETTE = re.compile(
    _START + rf"(?:{COLOUR_UTILITIES})(?:-[trblxy])?-(?:{TAILWIND_SCALES})-\d{{2,3}}\b"
)
ARBITRARY_COLOUR = re.compile(_START + rf"(?:{COLOUR_UTILITIES})(?:-[trblxy])?-\[#")

RADIUS = re.compile(
    r"(?<![\w\-\[])(?:[\w\-]+:)*rounded"
    r"(?:-(?:t|r|b|l|s|e|x|y|tl|tr|bl|br|ss|se|es|ee))?"
    r"(?:-([\w\[\]./]+))?(?![\w\-])"
)
ALLOWED_RADII = {"control", "card", "pill", "none"}

# Colour names the site's own palette uses; a utility naming one of these
# families must resolve to a defined colour (rule 4).
PALETTE_FAMILIES = (
    "carbon|electric|proton|iris|ink|body|muted|faint|danger|warn|success"
)
TOKEN_COLOUR = re.compile(
    _START + rf"(?:{COLOUR_UTILITIES})(?:-[trblxy])?-((?:{PALETTE_FAMILIES})(?:-[a-z]+)*)(?:/[\w.\[\]]+)?(?![\w\-])"
)


def _sources() -> list[Path]:
    return sorted(p for p in SRC.rglob("*") if p.suffix in {".tsx", ".ts"})


def _block(name: str) -> str:
    """The body of the ``name: { … }`` object in the Tailwind config."""
    text = CONFIG.read_text(encoding="utf-8")
    start = re.search(rf"\b{name}:\s*\{{", text)
    assert start, f"{name} block not found in {CONFIG}"
    depth, i = 1, start.end()
    while depth:
        depth += {"{": 1, "}": -1}.get(text[i], 0)
        i += 1
    return text[start.end() : i - 1]


def _keys(name: str) -> set[str]:
    # Top-level keys only: a fontSize entry's `{ lineHeight: … }` is not a key.
    body = re.sub(r"\{[^{}]*\}", "", _block(name))
    return set(re.findall(r"^\s*'?([\w-]+)'?\s*:", body, re.M))


def _token_values(name: str) -> dict[str, str]:
    return {
        k: v.lower()
        for k, v in re.findall(r"^\s*'?([\w-]+)'?\s*:\s*'(#[0-9A-Fa-f]{6})'", _block(name), re.M)
    }


# Class names only ever appear in string literals (`className="…"`, a
# template literal, a variant map's '…'). Scanning literals rather than whole
# lines keeps prose like "rounded outward" in JSX text and comments out of it.
_LITERAL = re.compile(r'"[^"\n]*"|`[^`]*`|\'[^\'\n]*\'')


def _matches(pattern: re.Pattern[str]):
    """Yield (location, match) for every match inside a string literal."""
    for path in _sources():
        text = path.read_text(encoding="utf-8")
        for lit in _LITERAL.finditer(text):
            for m in pattern.finditer(lit.group(0)):
                line = text.count("\n", 0, lit.start() + m.start()) + 1
                yield f"{path.relative_to(REPO_ROOT)}:{line}", m


def _hits(pattern: re.Pattern[str]) -> list[str]:
    return [f"{where}: {m.group(0)}" for where, m in _matches(pattern)]


def test_no_arbitrary_type_values() -> None:
    hits = _hits(ARBITRARY_TYPE)
    assert not hits, (
        "Arbitrary type values in site/src; use a named step from "
        "tailwind.config.ts (fontSize / lineHeight / letterSpacing), or add one "
        "and document it in site/DESIGN.md:\n  " + "\n  ".join(hits)
    )


def test_no_raw_palette_colours() -> None:
    hits = _hits(RAW_PALETTE) + _hits(ARBITRARY_COLOUR)
    assert not hits, (
        "Raw Tailwind palette or hex colours in site/src. Text is ink/body/"
        "muted/faint, verdicts are danger/warn/success, a measured result is "
        "proton (site/DESIGN.md):\n  " + "\n  ".join(hits)
    )


def test_only_named_radii() -> None:
    hits = [f"{where}: {m.group(0)}" for where, m in _matches(RADIUS) if m.group(1) not in ALLOWED_RADII]
    assert not hits, (
        "Radius outside rounded-control / rounded-card / rounded-pill. The "
        "config replaces Tailwind's radius scale, so these generate no CSS:\n  "
        + "\n  ".join(hits)
    )


def test_token_colour_classes_name_a_defined_colour() -> None:
    colours = _keys("colors")
    # `text-*` is also the font-size utility (`text-body-sm`, `text-caption`).
    sizes = _keys("fontSize")
    hits = [
        f"{where}: {m.group(0)}"
        for where, m in _matches(TOKEN_COLOUR)
        if m.group(1) not in colours
        and not (m.group(0).split(":")[-1].startswith("text-") and m.group(1) in sizes)
    ]
    assert not hits, (
        "Class names a colour tailwind.config.ts does not define, so it renders "
        "in whatever colour it inherits:\n  " + "\n  ".join(hits)
    )


def test_theme_color_meta_is_the_carbon_token() -> None:
    # The one hex literal the site needs outside CSS: a <meta> can't take a class.
    layout = (SRC / "app" / "layout.tsx").read_text(encoding="utf-8")
    meta = re.search(r'name="theme-color" content="(#[0-9a-fA-F]{6})"', layout)
    assert meta, "theme-color meta not found in app/layout.tsx"
    assert meta.group(1).lower() == _token_values("colors")["carbon"]


def test_design_doc_lists_every_token() -> None:
    doc = DESIGN_DOC.read_text(encoding="utf-8")
    missing = [
        f"{kind}: {key}"
        for kind in ("colors", "fontSize", "borderRadius")
        for key in sorted(_keys(kind))
        if key != "none" and f"`{key}`" not in doc
    ]
    assert not missing, (
        "Tokens in tailwind.config.ts that site/DESIGN.md does not document:\n  "
        + "\n  ".join(missing)
    )


def test_the_guards_catch_what_the_audit_found() -> None:
    # Each pattern must still match the drift it was written for.
    assert ARBITRARY_TYPE.search('className="md:text-[2.75rem] font-bold"')
    assert ARBITRARY_TYPE.search("tracking-[0.12em]")
    assert not ARBITRARY_TYPE.search("w-[1.625rem] min-w-[34rem]")
    assert RAW_PALETTE.search("hover:text-slate-300")
    assert RAW_PALETTE.search("bg-green-500/10")
    assert not RAW_PALETTE.search("text-electric-bright")
    assert ARBITRARY_COLOUR.search("bg-[#070b15]")
    assert RADIUS.search("rounded-xl").group(1) == "xl"
    assert RADIUS.search("p-4 rounded text-sm").group(1) is None
    assert RADIUS.search("md:rounded-t-lg").group(1) == "lg"
    assert TOKEN_COLOUR.search("text-electric-branch").group(1) == "electric-branch"
    assert TOKEN_COLOUR.search("bg-proton/[0.06]").group(1) == "proton"
