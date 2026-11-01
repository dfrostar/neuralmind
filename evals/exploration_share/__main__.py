"""CLI.

    python -m evals.exploration_share hermes --db ~/.hermes/state.db --since-days 30 --out rows.jsonl
    python -m evals.exploration_share claude-code --root ~/.claude/projects --since-days 30 --out rows.jsonl
    python -m evals.exploration_share report --rows rows.jsonl [more.jsonl] --out-md summary.md --out-json summary.json

Collectors write to ``--out`` and skip sessions already there, so a nightly run
over a window that overlaps the previous one adds only new sessions. A session whose
row was recorded before it finished (or that was resumed since) has written something
newer than its row holds: the next run collects it again and replaces its row.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from . import claude_code, hermes_db, report
from .tokens import Tokenizer


def _window(args) -> tuple[float, float]:
    # The window never reaches into the last --lag-hours, and the collectors defer
    # sessions still active at its end, so most rows are recorded once, finished. A row
    # recorded early anyway is replaced by the next run (see _write).
    latest = time.time() - args.lag_hours * 3600
    if args.since or args.until:
        since = _parse(args.since) if args.since else 0.0
        until = min(_parse(args.until), latest) if args.until else latest
        return since, until
    return latest - args.since_days * 86400, latest


def _parse(s: str) -> float:
    """ISO 8601; an explicit offset is kept, a timestamp without one is UTC."""
    dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.timestamp()


def _read(out: Path) -> list[dict]:
    if not out.exists():
        return []
    with out.open() as fh:
        return [json.loads(line) for line in fh if line.strip()]


def _recorded(existing: list[dict], agent: str) -> dict[str, float | None]:
    """Session id -> the latest activity its row holds. Rows from before `last_activity`
    existed fall back to `ended_at`, which is the last line for Claude Code; a row with
    neither is collected again once."""
    return {
        r["session_id"]: r.get("last_activity", r.get("ended_at"))
        for r in existing
        if r.get("agent") == agent
    }


def _dedupe(rows) -> list:
    """One row per (agent, session id): two transcript files can carry the same session id,
    and the first one, in path order, is the row, as ``report.read_rows`` has always kept."""
    first: dict[tuple[str, str], object] = {}
    for r in rows:
        first.setdefault((r.agent, r.session_id), r)
    return list(first.values())


def _write(out: Path, existing: list[dict], rows) -> tuple[int, int]:
    """Replace the rows of sessions collected again and add the new ones; (added, updated)."""
    fresh = {(r.agent, r.session_id): r.to_json() for r in rows}
    if not fresh:
        return 0, 0
    old = {(e.get("agent"), e["session_id"]) for e in existing}
    kept = [e for e in existing if (e.get("agent"), e["session_id"]) not in fresh]
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = out.with_name(out.name + ".tmp")
    with tmp.open("w") as fh:
        for r in [*kept, *fresh.values()]:
            fh.write(json.dumps(r, sort_keys=True) + "\n")
    os.replace(tmp, out)  # a run killed half-way leaves the previous file intact
    updated = len(fresh.keys() & old)
    return len(fresh) - updated, updated


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="python -m evals.exploration_share")
    sub = p.add_subparsers(dest="cmd", required=True)
    for name in ("hermes", "claude-code"):
        c = sub.add_parser(name)
        if name == "hermes":
            c.add_argument("--db", default="~/.hermes/state.db")
        else:
            c.add_argument("--root", default="~/.claude/projects")
        c.add_argument("--since-days", type=float, default=30)
        c.add_argument(
            "--lag-hours", type=float, default=0, help="end the window this long before now"
        )
        c.add_argument("--since", help="ISO timestamp, UTC")
        c.add_argument("--until", help="ISO timestamp, UTC")
        c.add_argument("--out", required=True)
        c.add_argument("--estimate", action="store_true", help="force chars/4 instead of tiktoken")
    r = sub.add_parser("report")
    r.add_argument("--rows", nargs="+", required=True)
    r.add_argument("--title", default="Exploration share")
    r.add_argument("--out-md")
    r.add_argument("--out-json")
    args = p.parse_args(argv)

    if args.cmd in ("hermes", "claude-code"):
        since, until = _window(args)
        out = Path(args.out).expanduser()
        existing = _read(out)
        recorded = _recorded(existing, "hermes" if args.cmd == "hermes" else "claude-code")
        tok = Tokenizer(force_estimate=args.estimate)
        if args.cmd == "hermes":
            rows = hermes_db.collect(args.db, since, until, tok, recorded=recorded)
        else:
            rows = claude_code.collect(args.root, since, until, tok, recorded=recorded)
        rows = _dedupe(rows)
        added, updated = _write(out, existing, rows)
        inter = [x for x in rows if x.source_group == "interactive"]
        print(
            f"{datetime.now(timezone.utc).date()} {args.cmd}: {added} sessions added, "
            f"{updated} updated ({len(inter)} interactive), tokenizer {tok.name}, window "
            f"{datetime.fromtimestamp(since, timezone.utc):%Y-%m-%d}..{datetime.fromtimestamp(until, timezone.utc):%Y-%m-%d}"
        )
        return 0

    rows = report.read_rows(args.rows)
    agg = report.aggregate(rows)
    if args.out_json:
        Path(args.out_json).expanduser().write_text(
            json.dumps(agg, indent=1, sort_keys=True) + "\n"
        )
    md = report.to_markdown(agg, args.title)
    if args.out_md:
        Path(args.out_md).expanduser().write_text(md)
    else:
        sys.stdout.write(md)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
