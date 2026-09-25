"""Docs CLI-path lint: every ``neuralmind <cmd> [<sub>]`` in current docs must exist.

Motivation: the v4.1.0 release notes and the Memory-Layer wiki documented
``neuralmind memory record/query/audit`` long after those verbs moved to
``neuralmind decisions`` — users copying the docs hit ``invalid choice`` and
empty results. This gate walks the **real parser** (``neuralmind.cli.build_parser``)
and fails when a current doc references a command or subcommand that does not
exist. (v4.2.1 remediation R3.)

Rules:
- Scanned: ``README.md``, ``docs/wiki/**/*.md``, ``docs/*.md``, and the newest
  ``docs/releases/RELEASE_NOTES_v*.md``. Older release notes are historical
  records and are intentionally excluded — corrections belong in erratum blocks.
- Fenced code blocks: a line in command position (optional ``$ `` prefix)
  referencing an unknown command, or a nonexistent subcommand of a known
  command, fails. A block containing ``cli-doc-skip`` is ignored.
- Inline ``code spans``: only checked when the first word is a *known* command
  (prose like "neuralmind is importable" is ignored).
- A second word that is path-like (``a/b.py``) is treated as a positional
  argument, not a subcommand.
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path

from neuralmind.cli import build_parser

REPO = Path(__file__).resolve().parents[1]

# ---------------------------------------------------------------------------
# Pre-existing drift allowlist (remediation R3b).
#
# Found 2026-09-20 by the first run of this gate: these pages reference
# commands that do NOT exist anywhere in neuralmind/cli.py. They describe
# audit reporting, licensing administration, and backend management — either
# planned features or a different tool's CLI. Removing/rewriting those docs
# is tracked as R3b; until then the commands are excused HERE (explicitly,
# with file provenance) so that any NEW drift still fails CI.
# ---------------------------------------------------------------------------
ALLOWED_MISSING_COMMANDS = {
    "audit-report",  # docs/wiki/Scheduling-Guide.md, docs/SECURITY-GUIDE.md
    "audit-export",  # docs/SECURITY-GUIDE.md
    "issue-license",  # docs/NEURALMIND-LICENSE-AGREEMENT.md
    "renew-license",  # docs/NEURALMIND-LICENSE-AGREEMENT.md
    "revoke-license",  # docs/NEURALMIND-LICENSE-AGREEMENT.md
    "license-status",  # docs/NEURALMIND-LICENSE-AGREEMENT.md
    "license-list",  # docs/NEURALMIND-LICENSE-AGREEMENT.md
    "backend-check",  # docs/wiki/FAQ.md, docs/DEPLOYMENT-GUIDE.md
    "backend-list",  # docs/UPGRADING.md
    "graphify",  # docs/DEPLOYMENT-GUIDE.md (legacy pre-rename CLI name)
}

_CMD = re.compile(r"^\s*(?:\$\s+)?neuralmind\s+([a-z][a-z0-9-]+)(?:\s+([a-z][a-z0-9-]+))?")


def _command_tree() -> dict[str, set[str]]:
    """Map first-level command -> set of its subcommands (empty for leaves)."""
    parser = build_parser()
    tree: dict[str, set[str]] = {}
    for action in parser._actions:
        if isinstance(action, argparse._SubParsersAction):
            for cmd, sub_parser in action.choices.items():
                children = [
                    a for a in sub_parser._actions if isinstance(a, argparse._SubParsersAction)
                ]
                tree[cmd] = set(children[0].choices) if children else set()
    return tree


def _finding(line: str, tree: dict[str, set[str]], *, inline: bool = False) -> str | None:
    m = _CMD.match(line)
    if not m:
        return None
    cmd, sub = m.group(1), m.group(2)
    if cmd not in tree:
        if inline or cmd in ALLOWED_MISSING_COMMANDS:
            return None  # prose ("neuralmind is importable") or R3b-excused page
        return f"`neuralmind {cmd}` — unknown command"
    subs = tree[cmd]
    if subs and sub and sub not in subs:
        rest = line[m.end(2) :]
        if "/" in sub or "." in sub or rest[:1] in ("/", "."):
            return None  # path-like positional, not a subcommand
        valid = ", ".join(sorted(subs))
        return (
            f"`neuralmind {cmd} {sub}` — '{sub}' is not a subcommand of "
            f"'{cmd}' (valid: {valid})"
        )
    return None


def _doc_files() -> list[Path]:
    releases = sorted(
        (REPO / "docs" / "releases").glob("RELEASE_NOTES_v*.md"),
        key=lambda p: [int(x) for x in re.findall(r"\d+", p.stem)][:4] or [0],
    )
    files = [REPO / "README.md"]
    files += sorted((REPO / "docs" / "wiki").rglob("*.md"))
    files += sorted((REPO / "docs").glob("*.md"))
    if releases:
        files.append(releases[-1])
    return files


def collect_violations() -> list[str]:
    tree = _command_tree()
    problems: list[str] = []
    for path in _doc_files():
        if not path.exists():
            continue
        rel = path.relative_to(REPO)
        text = path.read_text(errors="replace")
        for block in re.findall(r"```[^\n]*\n(.*?)```", text, re.DOTALL):
            if "cli-doc-skip" in block:
                continue
            for line in block.splitlines():
                found = _finding(line, tree)
                if found:
                    problems.append(f"{rel}: {found}\n    {line.strip()[:110]}")
        for span in re.findall(r"`([^`\n]*neuralmind[^`\n]*)`", text):
            found = _finding(span, tree, inline=True)
            if found:
                problems.append(f"{rel}: {found} (inline)\n    {span.strip()[:110]}")
    return problems


def test_docs_reference_only_existing_cli_commands():
    problems = collect_violations()
    assert not problems, (
        "Current docs reference CLI commands that do not exist.\n"
        "Fix the docs — or add the command to ALLOWED_MISSING_COMMANDS (with a "
        "provenance comment) only if it genuinely belongs to another tool/era:\n\n"
        + "\n".join(problems)
    )


def test_gate_catches_the_v41_drift_regression():
    """The gate must flag the exact class of reference it was built for."""
    tree = _command_tree()
    found = _finding("neuralmind memory audit . --stale-only", tree)
    assert found is not None and "is not a subcommand of 'memory'" in found


def test_gate_ignores_prose_and_paths():
    """No false positives on prose mentions or file-path positionals."""
    tree = _command_tree()
    assert _finding("neuralmind is importable", tree, inline=True) is None
    assert _finding("neuralmind review lib/utils/dose_conversion.dart", tree) is None
    assert _finding("cd test-neuralmind", tree) is None
