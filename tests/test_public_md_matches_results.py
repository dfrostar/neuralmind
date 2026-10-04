"""Guard the per-repo tables in ``docs/benchmarks/public.md`` against drift.

``tests/test_site_claims.py`` recomputes the site's headline from
``bench/public/results.json``, and the public-drift workflow compares a fresh
benchmark run against that same file. Neither reads the per-repo tables in
``docs/benchmarks/public.md`` — the page the README and the site's
``/benchmark`` page link to for the full numbers. Those tables are
hand-edited (``render_markdown`` prints no thousands separators, no bold
headline row, and no "vs full-file" column), so regenerating ``results.json``
without touching the page, or editing the page without regenerating, kept CI
green while the two disagreed.

This module parses every ``### `<repo>` @ `<sha>` — N pre-registered queries``
section and checks, against the committed run:

1. **Every cell of the results table** — recall and MRR to 2 decimals,
   found-rate as a whole percent, mean tokens to the nearest integer with
   commas, and ``full_tokens / backend_tokens`` to 1 decimal (``1×`` for
   ``full-file`` itself). Format specs mirror ``evals/public/run.py``'s
   ``render_markdown``, so the page rounds exactly the way the generator does.
2. **The heading** — the short SHA is a prefix of the run's pinned commit and
   the query count is the run's ``n_queries``.
3. **"Where it missed"** — the miss count, the query total, and each missed
   query's gold and retrieved files match the run's NeuralMind ``losses``.

Stdlib-only, like the other claims guards, so it runs without the full dep set.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
PUBLIC_MD = REPO_ROOT / "docs" / "benchmarks" / "public.md"
PUBLIC_RESULTS = REPO_ROOT / "bench" / "public" / "results.json"

# A floor, not the whole set: a parser that matches nothing must fail loudly
# instead of comparing zero rows and passing. A fifth repo in results.json is
# still required on the page by the set comparison in _mismatches.
REQUIRED_REPOS = ("requests", "click", "flask", "rich")
REQUIRED_BACKENDS = ("full-file", "ripgrep", "embedding-rag", "neuralmind")

RESULTS_HEADER = (
    "backend",
    "gold-file recall",
    "found-rate",
    "mean tokens/query",
    "MRR",
    "vs full-file",
)
MISSES_HEADER = ("query", "gold files", "files it retrieved")
COLUMNS = RESULTS_HEADER[1:]

# ### `requests` @ `0e322af877` — 14 pre-registered queries
REPO_HEADING_RE = re.compile(
    r"^### `(?P<repo>[^`]+)` @ `(?P<sha>[0-9a-f]+)` — (?P<n>\d+) pre-registered queries\s*$"
)
# Any other heading ("### Aggregate across…") closes the current repo section.
HEADING_RE = re.compile(r"^#{1,6} ")
SEPARATOR_RE = re.compile(r"^\|(\s*:?-+:?\s*\|)+\s*$")
BACKTICKED_RE = re.compile(r"^`([^`]+)`$")
MISSED_COUNT_RE = re.compile(r"^\*\*Where it missed\*\* \((?P<k>\d+) of (?P<n>\d+)\):\s*$")
# Repos with no misses use one of two phrasings ("none." or the sentence the
# generator prints); either counts as an explicit zero.
MISSED_NONE_RE = re.compile(
    r"^(\*\*Where it missed\*\*: none\.|No NeuralMind gold-file misses on this repo\.)\s*$"
)


def _results() -> dict:
    return json.loads(PUBLIC_RESULTS.read_text(encoding="utf-8"))


def _cells(line: str) -> list[str]:
    """Table cells with surrounding whitespace and bold markers removed."""
    return [c.strip().strip("*").strip() for c in line.strip()[1:-1].split("|")]


def _backticked(cell: str) -> str | None:
    m = BACKTICKED_RE.match(cell)
    return m.group(1) if m else None


def _files(cell: str) -> list[str]:
    """A file-list cell as names: `a.py`, `b.py` -> ["a.py", "b.py"]; "—" -> []."""
    if cell in ("", "—"):
        return []
    return [_backticked(part.strip()) or part.strip() for part in cell.split(",")]


def _parse_sections(text: str) -> list[dict]:
    """One dict per repo section of public.md, with 1-based line numbers."""
    sections: list[dict] = []
    current: dict | None = None
    table: str | None = None
    for lineno, line in enumerate(text.splitlines(), start=1):
        heading = REPO_HEADING_RE.match(line)
        if heading:
            current = {
                "repo": heading["repo"],
                "sha": heading["sha"],
                "n_queries": int(heading["n"]),
                "lineno": lineno,
                "header": None,
                "rows": [],
                "missed": None,
                "misses": [],
            }
            sections.append(current)
            table = None
            continue
        if current is None:
            continue
        if HEADING_RE.match(line):
            current = None
            continue
        if MISSED_NONE_RE.match(line):
            current["missed"] = (0, None)
            continue
        missed = MISSED_COUNT_RE.match(line)
        if missed:
            current["missed"] = (int(missed["k"]), int(missed["n"]))
            continue
        if not line.startswith("|"):
            table = None
            continue
        if SEPARATOR_RE.match(line):
            continue
        cells = _cells(line)
        if table is None:
            # The first row of a table is its header; it says which table this is.
            table = "results" if cells[0] == RESULTS_HEADER[0] else "misses"
            if table == "results":
                current["header"] = tuple(cells)
            continue
        if table == "results":
            current["rows"].append(
                {"backend": _backticked(cells[0]), "cells": tuple(cells[1:]), "lineno": lineno}
            )
        else:
            current["misses"].append(
                {
                    "query": _backticked(cells[0]),
                    "gold": _files(cells[1]) if len(cells) > 1 else [],
                    "retrieved": _files(cells[2]) if len(cells) > 2 else [],
                    "lineno": lineno,
                }
            )
    return sections


def _expected_cells(summary: dict, full_tokens: float, backend: str) -> tuple[str, ...]:
    """A backend's row the way public.md prints it."""
    if backend == "full-file":
        ratio = "1×"
    else:
        ratio = f"{full_tokens / summary['mean_tokens']:.1f}×"
    return (
        f"{summary['mean_recall']:.2f}",
        f"{summary['found_rate']:.0%}",
        f"{summary['mean_tokens']:,.0f}",
        f"{summary['mean_mrr']:.2f}",
        ratio,
    )


def _repo_mismatches(section: dict, run: dict, backends: list[str]) -> list[str]:
    name = section["repo"]
    where = f"public.md:{section['lineno']} `{name}`"
    problems: list[str] = []

    commit = run.get("commit") or ""
    if len(section["sha"]) < 7 or not commit.startswith(section["sha"]):
        problems.append(f"{where}: heading SHA {section['sha']} is not a prefix of {commit}")
    if section["n_queries"] != run["n_queries"]:
        problems.append(
            f"{where}: heading says {section['n_queries']} queries, "
            f"results.json has n_queries={run['n_queries']}"
        )

    if section["header"] != RESULTS_HEADER:
        problems.append(
            f"{where}: results table header is {section['header']!r}, "
            f"expected {RESULTS_HEADER!r} — columns can't be matched to results.json"
        )
        return problems

    rows = section["rows"]
    seen = [r["backend"] for r in rows]
    duplicates = sorted({b for b in seen if seen.count(b) > 1})
    if duplicates:
        problems.append(f"{where}: backend rows appear more than once: {duplicates}")
    missing = [b for b in backends if b not in seen]
    extra = [b for b in seen if b not in run["summary"]]
    if missing:
        problems.append(f"{where}: no table row for {missing}")
    if extra:
        problems.append(f"{where}: table rows for backends results.json lacks: {extra}")

    full_tokens = run["summary"]["full-file"]["mean_tokens"]
    for row in rows:
        summary = run["summary"].get(row["backend"])
        if summary is None:
            continue
        expected = _expected_cells(summary, full_tokens, row["backend"])
        if len(row["cells"]) != len(expected):
            problems.append(
                f"public.md:{row['lineno']} `{name}` / `{row['backend']}`: "
                f"{len(row['cells'])} value cells, expected {len(expected)}"
            )
            continue
        for column, page, data in zip(COLUMNS, row["cells"], expected, strict=True):
            if page != data:
                problems.append(
                    f"public.md:{row['lineno']} `{name}` / `{row['backend']}` {column}: "
                    f"page says {page}, results.json gives {data}"
                )

    losses = [loss for loss in run.get("losses", []) if loss["backend"] == "neuralmind"]
    if section["missed"] is None:
        problems.append(f"{where}: no 'Where it missed' line (count, 'none.', or no-misses note)")
    else:
        k, n = section["missed"]
        if k != len(losses):
            problems.append(
                f"{where}: 'Where it missed' says {k}, results.json has {len(losses)} losses"
            )
        if n is not None and n != run["n_queries"]:
            problems.append(
                f"{where}: 'Where it missed' says 'of {n}', "
                f"results.json has n_queries={run['n_queries']}"
            )
    page_misses = [(m["query"], m["gold"], m["retrieved"]) for m in section["misses"]]
    data_misses = [(x["query_id"], x["gold_files"], x["context_files"][:6]) for x in losses]
    if page_misses != data_misses:
        problems.append(
            f"{where}: 'Where it missed' rows {page_misses!r} "
            f"disagree with results.json losses {data_misses!r}"
        )
    return problems


def _mismatches(text: str, data: dict) -> list[str]:
    """Every disagreement between public.md's repo tables and results.json."""
    sections = _parse_sections(text)
    runs = {r["name"]: r for r in data["repos"]}
    problems: list[str] = []

    names = [s["repo"] for s in sections]
    for name in REQUIRED_REPOS:
        if name not in names:
            problems.append(f"public.md: no `### `{name}` @ …` section parsed")
        if name not in runs:
            problems.append(f"results.json: no run for required repo {name}")
    for name in sorted(set(runs) - set(names)):
        if name not in REQUIRED_REPOS:
            problems.append(f"public.md: results.json has {name}, the page has no section")
    for name in sorted({n for n in names if names.count(n) > 1}):
        problems.append(f"public.md: more than one section for `{name}`")

    backends = list(data.get("backends") or [])
    missing_backends = [b for b in REQUIRED_BACKENDS if b not in backends]
    if missing_backends:
        problems.append(f"results.json: backends list lacks {missing_backends}")

    for section in sections:
        run = runs.get(section["repo"])
        if run is None:
            problems.append(
                f"public.md:{section['lineno']}: section for `{section['repo']}`, "
                "which results.json has no run for"
            )
            continue
        problems.extend(_repo_mismatches(section, run, backends))
    return problems


def test_public_md_tables_match_results_json() -> None:
    problems = _mismatches(PUBLIC_MD.read_text(encoding="utf-8"), _results())
    assert not problems, (
        "docs/benchmarks/public.md disagrees with bench/public/results.json. "
        "Update the page from the committed run (or regenerate the run with "
        "python -m evals.public.run --out bench/public):\n  " + "\n  ".join(problems)
    )


def test_parser_finds_every_repo_and_backend() -> None:
    """A regex that silently matches nothing would make the guard vacuous."""
    sections = {s["repo"]: s for s in _parse_sections(PUBLIC_MD.read_text(encoding="utf-8"))}
    assert set(REQUIRED_REPOS) <= set(sections), sorted(sections)
    for name in REQUIRED_REPOS:
        backends = [r["backend"] for r in sections[name]["rows"]]
        assert set(REQUIRED_BACKENDS) <= set(backends), (name, backends)
        assert all(len(r["cells"]) == len(COLUMNS) for r in sections[name]["rows"]), name
        assert sections[name]["missed"] is not None, name
    total_misses = sum(len(s["misses"]) for s in sections.values())
    total_losses = sum(
        1 for r in _results()["repos"] for x in r["losses"] if x["backend"] == "neuralmind"
    )
    assert total_misses == total_losses


def _bump_last_digit(cell: str) -> str:
    """'41,729' -> '41,720', '**0.93**' -> '**0.94**', '1×' -> '2×'."""
    digits = [i for i, ch in enumerate(cell) if ch.isdigit()]
    i = digits[-1]
    return cell[:i] + str((int(cell[i]) + 1) % 10) + cell[i + 1 :]


def _with_cell_bumped(lines: list[str], lineno: int, column: int) -> str:
    """public.md text with one table cell (0 = first column) nudged by one digit."""
    line = lines[lineno - 1]
    parts = line.split("|")
    parts[column + 1] = _bump_last_digit(parts[column + 1])
    mutated = list(lines)
    mutated[lineno - 1] = "|".join(parts)
    return "\n".join(mutated)


def test_guard_trips_on_any_single_changed_number() -> None:
    """Change any one number in a repo table, heading, or miss count: CI must fail."""
    text = PUBLIC_MD.read_text(encoding="utf-8")
    data = _results()
    lines = text.splitlines()
    sections = _parse_sections(text)
    survivors: list[str] = []
    mutations = 0

    for section in sections:
        for row in section["rows"]:
            for column in range(1, len(RESULTS_HEADER)):
                mutations += 1
                if not _mismatches(_with_cell_bumped(lines, row["lineno"], column), data):
                    survivors.append(f"line {row['lineno']} {RESULTS_HEADER[column]}")
        heading = lines[section["lineno"] - 1]
        for old, label in (
            (f"@ `{section['sha']}`", "SHA"),
            (f"— {section['n_queries']} pre", "query count"),
        ):
            mutations += 1
            mutated = list(lines)
            mutated[section["lineno"] - 1] = heading.replace(old, _bump_last_digit(old), 1)
            if not _mismatches("\n".join(mutated), data):
                survivors.append(f"line {section['lineno']} heading {label}")

    for lineno, line in enumerate(lines, start=1):
        m = MISSED_COUNT_RE.match(line)
        if not m:
            continue
        for group in ("k", "n"):
            mutations += 1
            mutated = list(lines)
            start, end = m.span(group)
            mutated[lineno - 1] = line[:start] + _bump_last_digit(m[group]) + line[end:]
            if not _mismatches("\n".join(mutated), data):
                survivors.append(f"line {lineno} 'Where it missed' {group}")

    # 4 repos x 4 backends x 5 columns, plus 2 heading numbers per repo.
    assert mutations >= len(REQUIRED_REPOS) * (len(REQUIRED_BACKENDS) * len(COLUMNS) + 2)
    assert not survivors, f"Mutations the guard did not catch: {survivors}"


def test_guard_catches_a_regenerated_run_with_a_stale_page() -> None:
    """The reverse direction: results.json moves, the page doesn't."""
    text = PUBLIC_MD.read_text(encoding="utf-8")
    data = _results()
    data["repos"][0]["summary"]["neuralmind"]["mean_tokens"] += 50
    problems = _mismatches(text, data)
    assert any("mean tokens/query" in p for p in problems), problems
    assert any("vs full-file" in p for p in problems), problems


def test_guard_rejects_a_page_with_no_parseable_sections() -> None:
    problems = _mismatches("# NeuralMind\n\nNo tables here.\n", _results())
    assert sum("section parsed" in p for p in problems) == len(REQUIRED_REPOS), problems


def test_formatting_matches_how_the_page_prints() -> None:
    summary = {
        "mean_recall": 0.9286,
        "found_rate": 0.8571,
        "mean_tokens": 927.9,
        "mean_mrr": 0.9167,
    }
    assert _expected_cells(summary, 41729, "neuralmind") == ("0.93", "86%", "928", "0.92", "45.0×")
    full = {"mean_recall": 1.0, "found_rate": 1.0, "mean_tokens": 232483, "mean_mrr": 1.0}
    assert _expected_cells(full, 232483, "full-file") == ("1.00", "100%", "232,483", "1.00", "1×")
    assert _files("`sessions.py`, `auth.py`") == ["sessions.py", "auth.py"]
    assert _bump_last_digit("**0.93**") == "**0.94**" and _bump_last_digit("1×") == "2×"
