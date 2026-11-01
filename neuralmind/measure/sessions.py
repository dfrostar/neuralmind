# SPDX-License-Identifier: MIT
"""``neuralmind measure sessions``: find the agents' session stores and measure them.

Everything here is read-only. What leaves this module is aggregates; per-session
rows (:func:`write_rows`) go only to a path the user names.
"""

from __future__ import annotations

import json
import os
import sqlite3
import time
from dataclasses import dataclass, field
from pathlib import Path

from . import claude_code, hermes_db, report
from .rows import SessionRow
from .tokens import Tokenizer

CLAUDE_CODE = "claude-code"
HERMES = "hermes"

READ = "read"
NOT_FOUND = "not found"
UNREADABLE = "unreadable"


def default_claude_root() -> Path:
    """Where Claude Code keeps transcripts: ``$CLAUDE_CONFIG_DIR/projects``, else ``~/.claude/projects``."""
    configured = os.environ.get("CLAUDE_CONFIG_DIR", "").strip()
    base = Path(configured).expanduser() if configured else Path.home() / ".claude"
    return base / "projects"


def default_hermes_db() -> Path:
    """Hermes's ``state.db``, in the home plain ``hermes`` runs in (``$HERMES_HOME``, the active profile)."""
    from neuralmind.hermes_install import hermes_home

    return hermes_home() / "state.db"


@dataclass
class Measurement:
    rows: list[SessionRow] = field(default_factory=list)
    sources: dict[str, str] = field(default_factory=dict)  # name -> READ | NOT_FOUND | UNREADABLE
    warnings: list[str] = field(default_factory=list)  # for stderr; no paths


def measure(
    claude_root: str | Path | None,
    hermes_db_path: str | Path | None,
    since: float,
    until: float,
    tokenizer: Tokenizer,
) -> Measurement:
    """Collect the sessions that started in ``[since, until)`` from each source that exists.

    A source that is missing is skipped; one that is there but can't be read is
    reported in ``warnings`` and skipped, so the other still gets measured.
    """
    out = Measurement()

    root = Path(claude_root).expanduser() if claude_root else default_claude_root()
    if not root.is_dir():
        out.sources[CLAUDE_CODE] = NOT_FOUND
    else:
        unreadable: list[Exception] = []
        try:
            out.rows += claude_code.collect(
                root, since, until, tokenizer, on_error=lambda _path, exc: unreadable.append(exc)
            )
            out.sources[CLAUDE_CODE] = READ
        except OSError as exc:  # the directory itself
            out.sources[CLAUDE_CODE] = UNREADABLE
            out.warnings.append(
                f"Claude Code transcripts could not be read ({exc.strerror or type(exc).__name__})."
            )
        if unreadable:
            out.warnings.append(
                f"Skipped {len(unreadable)} Claude Code transcript(s) that could not be read."
            )

    db = Path(hermes_db_path).expanduser() if hermes_db_path else default_hermes_db()
    if not db.is_file():
        out.sources[HERMES] = NOT_FOUND
    else:
        try:
            out.rows += hermes_db.collect(db, since, until, tokenizer)
            out.sources[HERMES] = READ
        except (sqlite3.Error, OSError) as exc:
            out.sources[HERMES] = UNREADABLE
            # an OSError's own text names the path
            reason = exc.strerror if isinstance(exc, OSError) and exc.strerror else str(exc)
            out.warnings.append(f"Hermes state.db could not be read ({reason}).")
    return out


def window(since_days: float, now: float | None = None) -> tuple[float, float]:
    until = time.time() if now is None else now
    return max(0.0, until - since_days * 86400), until


def summarize(m: Measurement, since: float, until: float, tokenizer: Tokenizer) -> dict:
    """The aggregate (what ``report`` computes), plus the window and which sources were read."""
    agg = report.aggregate([r.to_json() for r in m.rows])
    agg["window"] = {
        "since": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(since)),
        "until": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(until)),
    }
    agg["sources"] = dict(m.sources)
    agg["tokenizer"] = tokenizer.name
    return agg


def write_rows(path: str | Path, rows: list[SessionRow]) -> int:
    """Per-session rows as JSON lines, replacing the file. Returns how many were written."""
    dest = Path(path).expanduser()
    dest.parent.mkdir(parents=True, exist_ok=True)
    with dest.open("w", encoding="utf-8") as fh:
        for r in rows:
            fh.write(json.dumps(r.to_json(), sort_keys=True) + "\n")
    return len(rows)


SPEC_URL = "https://github.com/dfrostar/neuralmind/blob/main/docs/specs/EXPLORATION-SHARE-SPEC.md"
_SOURCE_NAMES = {CLAUDE_CODE: "Claude Code", HERMES: "Hermes"}


def describe_sources(sources: dict[str, str]) -> str:
    """``Claude Code: read; Hermes: not found``: no paths."""
    return "; ".join(f"{_SOURCE_NAMES[k]}: {v}" for k, v in sources.items())


def render(agg: dict, since_days: float) -> str:
    """The terminal report for a :func:`summarize` result. Aggregates only."""
    sources = describe_sources(agg["sources"])
    return (
        "Exploration share of the token bill\n"
        f"Sessions started {agg['window']['since'][:10]} to {agg['window']['until'][:10]} "
        f"(last {since_days:g} days). {sources}.\n\n" + report.to_text(agg) + "\n"
        "Exploration is reading and searching code: Read, Grep, Glob and read-only shell\n"
        "commands. 'Of context' is the spec's headline: the exploration tokens each API\n"
        "call carried over everything the transcripts record it carrying, both counted\n"
        "one way. 'Of billed prompt' divides the same tokens by what the provider billed,\n"
        "and 'Recorded / billed' is how much of that bill the transcripts account for.\n"
        "Automated, subagent and benchmark sessions are shown, never read against the\n"
        "thresholds; read a share with its session count beside it.\n"
        "Definitions, limits and the thresholds, fixed before any share was computed:\n"
        f"{SPEC_URL}\n"
        "This measures where the tokens went. It doesn't estimate what any tool would change.\n"
    )
