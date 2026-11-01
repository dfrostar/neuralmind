"""Each Hermes run's whole-session usage, read from Hermes's state.db.

    python -m evals.task_outcome.hermes_sessions <out_dir> [--state-db PATH]

Writes ``<out_dir>/sessions.json``, which ``analyze`` uses for a Hermes run's
tokens and minutes. A run's record can't give them on one scale:

* Its tokens come from the Hermes client's ``result`` event, which covers the
  client's own turn. A background command that finishes later wakes the
  session for more turns, and the tests judge the workspace after those.
* A run cut off by the timeout has no ``result`` event. The runner took the
  session row's ``input_tokens`` instead, which leave out cache reads, most
  of a prompt's tokens.
* A timed-out run has no duration either.

The session row covers every turn. ``prompt_tokens`` here is its uncached
input plus cache reads and writes, which is what a ``result`` event's input
counts; ``minutes`` runs from the session's start to its last activity.

Read-only; stdlib only, so it runs on the benchmark machine from a copy.
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from pathlib import Path

HERMES_STATE_DB = Path.home() / ".hermes" / "state.db"


def session_usage(session_ids: list[str], state_db: Path) -> dict[str, dict]:
    """``{session_id: usage}`` for each id the database holds."""
    db = sqlite3.connect(f"file:{state_db}?mode=ro", uri=True)
    try:
        out = {}
        for sid in session_ids:
            row = db.execute(
                "SELECT api_call_count, input_tokens, cache_read_tokens, cache_write_tokens,"
                " output_tokens, started_at, last_activity_at FROM sessions WHERE id = ?",
                (sid,),
            ).fetchone()
            if row is None:
                continue
            calls, uncached, read, write, output, started, last = row
            out[sid] = {
                "api_calls": calls,
                "prompt_tokens": (uncached or 0) + (read or 0) + (write or 0),
                "output_tokens": output or 0,
                "minutes": None if started is None or last is None else (last - started) / 60,
            }
        return out
    finally:
        db.close()


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("out_dir", type=Path)
    ap.add_argument("--state-db", type=Path, default=HERMES_STATE_DB)
    args = ap.parse_args(argv)
    runs = [
        json.loads(line) for line in (args.out_dir / "runs.jsonl").read_text().splitlines() if line
    ]
    ids = [r["session_id"] for r in runs if r.get("agent") == "hermes" and r.get("session_id")]
    usage = session_usage(ids, args.state_db)
    (args.out_dir / "sessions.json").write_text(json.dumps(usage, indent=1, sort_keys=True) + "\n")
    missing = len(ids) - len(usage)
    print(f"{len(usage)} session(s) written; {missing} not in {args.state_db}")
    return 1 if missing else 0


if __name__ == "__main__":
    sys.exit(main())
