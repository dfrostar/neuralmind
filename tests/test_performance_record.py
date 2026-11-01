"""Guard the longitudinal performance record behind /performance.

The site guards in ``tests/test_site_claims.py`` read TSX. /performance types
no numbers: it renders the rows of ``benchmarks/ai9970/record.jsonl`` and the
monthly narratives beside it, and the narratives' blocks A and C go on the page
and block B to https://neuralmind.uk/performance/linkedin.txt. Without this
module, hand-written copy would reach both with no guard reading it.

1. **Narratives pass the site's rules** — no absolute privacy claims, no
   overclaims, no perfect-recall claims, no unsourced or superseded figures,
   no bare 12–50×, and every ratio either listed in ``site/claims.json`` or
   the ratio of a measured record row with its baseline recorded (the only
   ratios the page itself would show). Every block is published, so every
   block is read.
2. **No integrity notes in this repo.** It is public on GitHub, so notes on how
   the rows were produced live in the private repo ``site/claims.json`` names
   (``longitudinal_record.integrity_notes``). A ``## D`` block, a heading that
   names integrity, or a file named for it under ``benchmarks/ai9970/`` fails.
3. **No private names** in the record, the profile or the narratives.
4. **The canon names files that exist.**

Row-level arithmetic (rates against gold-set size, ratio against baseline and
context tokens) is checked where the rows are rendered, in
``site/src/lib/record.ts``; the site build fails on a row that breaks it.

Stdlib-only, like the other claims guards.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from tests.test_docs_claims import (
    FORBIDDEN,
    SUPERSEDED_FIGURES,
    UNSOURCED_FIGURES,
    _paragraph_before,
    _without_ranges,
    overclaims_in,
    unscoped_12_50,
)
from tests.test_site_claims import (
    ALLOW_MARKER,
    MIN_CLAIM_RATIO,
    PERFECT_RECALL_RE,
    _allowed_ratios,
    _claims,
    _ratio_claims_in,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
RECORD = _claims()["longitudinal_record"]
NARRATIVE_FILE_RE = re.compile(r"^\d{4}-\d{2}\.md$")
# The same headings site/src/lib/record.ts splits on and rejects.
BLOCK_RE = re.compile(r"^##\s+([A-Z])\b")
HEADING_RE = re.compile(r"^\s{0,3}#{1,6}(\s|$)")
D_BLOCK_RE = re.compile(r"^##\s+D\b")


def _rows() -> list[dict]:
    text = (REPO_ROOT / RECORD["source"]).read_text(encoding="utf-8")
    return [json.loads(line) for line in text.splitlines() if line.strip()]


def _measured_ratios(rows: list[dict]) -> set[float]:
    """Ratios /performance shows: a measured baseline, with its size recorded."""
    return {
        float(r["ratio_vs_indexed"])
        for r in rows
        if r.get("baseline_src") == "measured"
        and r.get("baseline_tok") is not None
        and r.get("ratio_vs_indexed") is not None
    }


def published_lines(text: str) -> list[str]:
    """Every line from the first block heading on; the title above it is dropped."""
    out: list[str] = []
    started = False
    for line in text.splitlines():
        if BLOCK_RE.match(line):
            started = True
            out.append("")  # a block boundary ends the paragraph
            continue
        if started:
            out.append(line)
    return out


def integrity_headings(text: str) -> list[int]:
    """Line numbers of headings that hold integrity notes: a ``## D`` block, or any
    heading naming integrity."""
    return [
        i
        for i, line in enumerate(text.splitlines(), start=1)
        if HEADING_RE.match(line) and ("integrity" in line.lower() or D_BLOCK_RE.match(line))
    ]


def violations_in(lines: list[str], allowed_ratios: set[float]) -> list[str]:
    """Every site-rule breach in a narrative's published lines, as "line N: why"."""
    found: list[str] = []
    for i, line in enumerate(lines):
        if ALLOW_MARKER in line or (i and ALLOW_MARKER in lines[i - 1]):
            continue
        where = f"line {i + 1}"
        for pattern, reason in FORBIDDEN:
            if m := pattern.search(line):
                found.append(f"{where}: {m.group(0)!r} — {reason}")
        for text, reason in overclaims_in(line, _paragraph_before(lines, i)):
            found.append(f"{where}: {text!r} — {reason}")
        for pattern, reason in UNSOURCED_FIGURES:
            if m := pattern.search(line):
                found.append(f"{where}: {m.group(0)!r} — {reason}")
        for pattern, reason in SUPERSEDED_FIGURES:
            if m := pattern.search(_without_ranges(line)):
                found.append(f"{where}: {m.group(0)!r} — {reason}")
        if m := PERFECT_RECALL_RE.search(line):
            found.append(
                f"{where}: {m.group(0)!r} — a perfect-recall claim; say how many of how "
                "many, as the site does"
            )
        if unscoped_12_50(lines, i):
            found.append(f"{where}: 12–50× without its fixed-50K baseline")
        for _, ratio in _ratio_claims_in(line):
            if ratio >= MIN_CLAIM_RATIO and ratio not in allowed_ratios:
                found.append(
                    f"{where}: {ratio:g}× is neither in site/claims.json nor a measured "
                    "row's ratio_vs_indexed with its baseline_tok recorded"
                )
    return found


def _narratives() -> list[Path]:
    folder = REPO_ROOT / RECORD["narratives"]
    return sorted(p for p in folder.iterdir() if NARRATIVE_FILE_RE.match(p.name))


def test_canon_names_files_that_exist() -> None:
    for key in ("source", "profile", "narratives"):
        assert (REPO_ROOT / RECORD[key]).exists(), f"site/claims.json longitudinal_record.{key}"
    assert RECORD["evidence"] in _claims()["_evidence_levels"]


def test_no_integrity_notes_in_the_public_repo() -> None:
    folder = REPO_ROOT / RECORD["source"]
    record_dir = folder.parent
    problems = [
        f"{path.relative_to(REPO_ROOT)}: a file named for integrity notes"
        for path in record_dir.rglob("*")
        if "integrity" in path.name.lower()
    ]
    for path in sorted((REPO_ROOT / RECORD["narratives"]).iterdir()):
        problems.extend(
            f"{path.relative_to(REPO_ROOT)}:{n}: an integrity heading"
            for n in integrity_headings(path.read_text(encoding="utf-8"))
        )
    assert not problems, (
        "Integrity notes are committed to this public repo. Keep them in "
        f"{RECORD['integrity_notes']}:\n  " + "\n  ".join(problems)
    )


def test_published_narrative_blocks_follow_the_site_rules() -> None:
    allowed = _allowed_ratios() | _measured_ratios(_rows())
    problems = [
        f"{path.relative_to(REPO_ROOT)} {v}"
        for path in _narratives()
        for v in violations_in(published_lines(path.read_text(encoding="utf-8")), allowed)
    ]
    assert not problems, (
        "A narrative block that /performance or linkedin.txt publishes breaks a "
        "site claims rule:\n  " + "\n  ".join(problems)
    )


def test_record_and_narratives_name_no_private_project() -> None:
    names = [n.lower() for n in _claims()["private_names_never_publish"]]
    files = [REPO_ROOT / RECORD["source"], REPO_ROOT / RECORD["profile"], *_narratives()]
    problems = [
        f"{path.relative_to(REPO_ROOT)} names {name!r}"
        for path in files
        for name in names
        if name in path.read_text(encoding="utf-8").lower()
    ]
    assert not problems, "\n".join(problems)


def test_guards_trip_on_bad_narrative_copy() -> None:
    rows = [
        {"ratio_vs_indexed": 60.3, "baseline_src": "measured", "baseline_tok": 52218},
        {"ratio_vs_indexed": 273.0, "baseline_src": "measured", "baseline_tok": None},
        {"ratio_vs_indexed": 41.8, "baseline_src": "naive-50k", "baseline_tok": 50000},
    ]
    allowed = _allowed_ratios() | _measured_ratios(rows)
    narrative = "\n".join(
        [
            "# 2026-10",
            "## A. Site",
            "rfnode-guide ran at 60.3× fewer tokens than its indexed code.",
            "## B. LinkedIn",
            "NeuralMind gets smarter with every session.",
            "## C. What we are working on",
            "- [stalled] bible-llm at 273.0× — its baseline size is not recorded.",
            "Zero code egress, and 999× once on a warm cache.",
            "NeuralMind has 100% gold-file recall on both repos.",
        ]
    )
    found = violations_in(published_lines(narrative), allowed)
    joined = "\n".join(found)
    # A measured ratio with its baseline passes.
    assert "60.3" not in joined
    # Block B's overclaim, block C's ratio without a recorded baseline, and
    # every block's absolutes and unsourced ratios fail.
    assert "smarter" in joined
    assert "273×" in joined
    assert "egress" in joined and "999×" in joined
    # The site's perfect-recall rule applies to every block too.
    assert "perfect-recall" in joined
    assert not violations_in(["## A", "The gold file is in the top five for 10 of 12."], allowed)
    # The title above block A is not published copy.
    assert published_lines("# 999× title\n## A\nText.") == ["", "Text."]
    # A synthetic-baseline row's ratio is never quotable.
    assert 41.8 not in _measured_ratios(rows)
    # The opt-out marker covers its own line and the next.
    marked = published_lines(
        "## A\n<!-- claims-guard:allow -->\nZero code egress, quoted to disown it."
    )
    assert violations_in(marked, allowed) == []


def test_integrity_guard_trips_on_notes_in_any_heading_form() -> None:
    for text, line in (
        ("## A\nText.\n## D. Integrity\nRe-ran once.", 3),
        ("## A\nText.\n## D\nRe-ran once.", 3),
        ("## C\n- [moved] x\n### Integrity notes\nRe-ran once.", 3),
        ("# 2026-10 integrity\n## A\nText.", 1),
    ):
        assert integrity_headings(text) == [line], text
    # Prose that mentions the word, and block A–C headings, are fine.
    clean = "## A. Site\nIntegrity of the rows is checked privately.\n## B. LinkedIn\n## C. Work"
    assert integrity_headings(clean) == []
    assert "neuralmind-marketing" in RECORD["integrity_notes"]
