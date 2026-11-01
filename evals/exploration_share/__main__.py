"""CLI.

    python -m evals.exploration_share hermes --db ~/.hermes/state.db --since-days 30 --out rows.jsonl
    python -m evals.exploration_share claude-code --root ~/.claude/projects --since-days 30 --out rows.jsonl
    python -m evals.exploration_share report --rows rows.jsonl [more.jsonl] --out-md summary.md --out-json summary.json

Collectors append to ``--out`` and skip session ids already there, so a nightly
run over a window that overlaps the previous one adds only new sessions.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from . import claude_code, hermes_db, report
from .tokens import Tokenizer


def _window(args) -> tuple[float, float]:
    if args.since or args.until:
        since = _parse(args.since) if args.since else 0.0
        until = _parse(args.until) if args.until else time.time()
        return since, until
    # A nightly run leaves out the newest sessions (--lag-hours), which may still
    # be running: a session is collected once and never updated.
    until = time.time() - args.lag_hours * 3600
    return until - args.since_days * 86400, until


def _parse(s: str) -> float:
    return (
        datetime.fromisoformat(s.replace("Z", "+00:00"))
        .replace(tzinfo=timezone.utc if "T" not in s or s.endswith("Z") else None)
        .timestamp()
    )


def _existing_ids(out: Path) -> set[str]:
    if not out.exists():
        return set()
    ids = set()
    with out.open() as fh:
        for line in fh:
            if line.strip():
                ids.add(json.loads(line)["session_id"])
    return ids


def _append(out: Path, rows) -> int:
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("a") as fh:
        for r in rows:
            fh.write(json.dumps(r.to_json(), sort_keys=True) + "\n")
    return len(rows)


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
            "--lag-hours", type=float, default=0, help="leave out sessions started this recently"
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
        skip = _existing_ids(out)
        tok = Tokenizer(force_estimate=args.estimate)
        if args.cmd == "hermes":
            rows = hermes_db.collect(args.db, since, until, tok, skip_ids=skip)
        else:
            rows = claude_code.collect(args.root, since, until, tok, skip_ids=skip)
        n = _append(out, rows)
        inter = [x for x in rows if x.source_group == "interactive"]
        print(
            f"{datetime.now(timezone.utc).date()} {args.cmd}: {n} sessions added "
            f"({len(inter)} interactive), tokenizer {tok.name}, window "
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
