"""Session-start hook latency on a synapse store: what an agent waits for at a session's start.

The Hermes plugin runs ``neuralmind _hook session-start`` on a session's first
turn and stops it after 8 s (``NEURALMIND_HERMES_TIMEOUT``), dropping the
recap it wrote; Claude Code's ``SessionStart`` hook is the same process. On a
large store its decay tick and memory export now run in a detached process
after it returns (:mod:`neuralmind.session_maintenance`), so this measures two
things per sample, one fresh process each:

- ``hook``: the call as the agent sees it, from start to exit.
- ``done``: from the same start until the store work is finished: the
  detached process has released its lock, or, for a NeuralMind that does that
  work inside the hook, the hook has exited.

It needs a project with a synapse store, and its numbers depend on the store
and the machine, so a result names both. **The hook writes to the project**,
as a session start does: it runs a decay tick, clears the ``ephemeral``
namespace and rewrites ``SYNAPSE_MEMORY.md``. Run it on a copy (on APFS,
``cp -cR`` clones a large index instantly). The same harness times another
NeuralMind by its interpreter (``--python``) or a checkout on ``PYTHONPATH``.

Run it::

    python -m tests.benchmark.session_start_latency <project-copy> --runs 5
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import sqlite3
import statistics
import sys
import time
from pathlib import Path
from typing import Any

from tests.benchmark.hook_latency import PLUGIN_TIMEOUT, _child, _identity, _load_average

# session_maintenance.LOCK_FILENAME; spelled out so --python can time a
# NeuralMind that predates it.
LOCK_FILENAME = "session_maintenance.lock"
# How long a detached process may take to start, and to finish.
START_WAIT = 3.0
DONE_TIMEOUT = 300.0


def _held(lock: Path) -> bool:
    """Whether a maintenance process holds ``lock`` now."""
    from neuralmind import graph_cache

    try:
        fd = os.open(lock, os.O_RDWR)
    except OSError:
        return False
    try:
        return not graph_cache._try_lock(fd)
    finally:
        os.close(fd)  # closing releases a lock taken here


def _maintenance_end(project: Path) -> float | None:
    """When the detached process released its lock; None when none took it.

    A NeuralMind that does the work inside the hook starts none, and a small
    store is maintained inside the hook too.
    """
    lock = project / ".neuralmind" / LOCK_FILENAME
    started_by = time.monotonic() + START_WAIT
    finished_by = time.monotonic() + DONE_TIMEOUT
    seen = False
    while time.monotonic() < finished_by:
        if _held(lock):
            seen = True
        elif seen:
            return time.perf_counter()
        elif time.monotonic() > started_by:
            return None
        time.sleep(0.01)
    raise TimeoutError(f"maintenance still running after {DONE_TIMEOUT:.0f} s")


def _sample(python: str, project: Path, env: dict[str, str], n: int) -> dict[str, Any]:
    payload = json.dumps(
        {"cwd": str(project), "session_id": f"session-start-latency-{n}", "source": "startup"}
    )
    start = time.perf_counter()
    out, hook = _child(python, "-m", "neuralmind", "_hook", "session-start", env=env, stdin=payload)
    end = _maintenance_end(project)
    done = hook if end is None else end - start
    try:
        recap = json.loads(out)["hookSpecificOutput"]["additionalContext"]
    except (ValueError, KeyError, TypeError):
        recap = ""
    return {"hook_s": hook, "done_s": done, "recap_chars": len(recap)}


def run(
    project: Path, *, runs: int = 5, python: str = sys.executable, label: str | None = None
) -> dict[str, Any]:
    project = project.resolve()
    env = dict(os.environ)
    for name in ("NEURALMIND_NO_LEARN", "NEURALMIND_SYNAPSE_EXPORT", "NEURALMIND_BYPASS"):
        env.pop(name, None)
    # First: it also probes the interpreter, which a timed call shouldn't include.
    identity = _identity(python, env)
    samples = [_sample(python, project, env, n) for n in range(runs)]
    report: dict[str, Any] = {
        "project": label or project.name,
        "machine": {
            "platform": platform.platform(),
            "processor": platform.processor() or platform.machine(),
            "cpus": os.cpu_count(),
            "load_average": _load_average(),
        },
        "neuralmind": identity,
        "plugin_timeout_s": PLUGIN_TIMEOUT,
        "store": _store_shape(project),
        "recap_chars": sorted({s["recap_chars"] for s in samples}),
    }
    for key in ("hook_s", "done_s"):
        values = [s[key] for s in samples]
        report[key] = {
            "mean": round(statistics.mean(values), 2),
            "min": round(min(values), 2),
            "max": round(max(values), 2),
            "samples": [round(v, 2) for v in values],
        }
    report["hook_s"]["within_plugin_timeout"] = sum(s["hook_s"] < PLUGIN_TIMEOUT for s in samples)
    return report


def _store_shape(project: Path) -> dict[str, Any]:
    db = project / ".neuralmind" / "synapses.db"
    shape: dict[str, Any] = {}
    try:
        shape["synapses_db_mb"] = round(db.stat().st_size / 1e6)
        conn = sqlite3.connect(f"{db.as_uri()}?mode=ro", uri=True)
        try:
            for table in ("synapses", "synapse_transitions", "node_activations"):
                shape[table] = conn.execute(
                    f"SELECT COUNT(*) FROM {table}"  # nosec B608 - fixed table names
                ).fetchone()[0]
        finally:
            conn.close()
    except (OSError, sqlite3.Error):
        pass
    return shape


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("project", type=Path, help="a copy of a project with a synapse store")
    parser.add_argument("--label", help="the project's name in the report")
    parser.add_argument("--runs", type=int, default=5)
    parser.add_argument("--python", default=sys.executable, help="interpreter to run the hook")
    parser.add_argument("--json", action="store_true", help="emit the raw report")
    parser.add_argument("--out", type=Path, help="also write the report here")
    args = parser.parse_args()

    report = run(args.project, runs=args.runs, python=args.python, label=args.label)
    if args.out:
        args.out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    if args.json:
        print(json.dumps(report, indent=2))
        return
    store = report["store"]
    print(
        f"session-start hook — {report['project']}: {store.get('synapses', '?'):,} synapse "
        f"edges, {store.get('synapses_db_mb', '?')} MB store; "
        f"NeuralMind {report['neuralmind'].get('version')} "
        f"({report['neuralmind'].get('commit')})\n"
    )
    print(f"{'':<8}{'mean (s)':>10}{'min (s)':>10}{'max (s)':>10}")
    for key, name in (("hook_s", "hook"), ("done_s", "done")):
        row = report[key]
        print(f"{name:<8}{row['mean']:>10.2f}{row['min']:>10.2f}{row['max']:>10.2f}")
    print(
        f"\nhook under {PLUGIN_TIMEOUT:.0f} s: {report['hook_s']['within_plugin_timeout']}/"
        f"{args.runs}; recap length: {', '.join(map(str, report['recap_chars']))} chars"
    )


if __name__ == "__main__":
    main()
