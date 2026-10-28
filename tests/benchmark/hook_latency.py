"""Prompt-submit hook latency on a built index: what an agent waits for each turn.

The Hermes plugin runs ``neuralmind _hook prompt-submit`` as a new process on
every turn and stops it after 8 s (``NEURALMIND_HERMES_TIMEOUT``); Claude
Code's ``UserPromptSubmit`` hook is the same process. On a large index that
process spent most of its time loading the graph (see
:mod:`neuralmind.graph_cache`), so this measures the whole call, as the agent
sees it: interpreter start, imports, index load, recall and the decisions
block, one fresh process per sample.

``latency.py`` beside it measures the synapse layer alone, which is stdlib-only
and reproducible anywhere. This one needs a built project, and its numbers
depend on the index and the machine, so a result names both.

States, each measured ``--runs`` times:

- ``uncached``: ``NEURALMIND_GRAPH_CACHE=0``, so every call reads
  ``index_ir.json`` or ``graph.json`` as before the cache existed.
- ``miss``: the cache is deleted before each call. The call starts the
  background warmer and loads the graph itself (and writes the cache).
- ``cached``: the cache is current.

The hook runs with ``NEURALMIND_NO_LEARN=1``, so it records no metrics. The
same harness times another NeuralMind by its interpreter (``--python``) or a
checkout on ``PYTHONPATH``; that one ignores ``NEURALMIND_GRAPH_CACHE`` if it
predates the cache, so pass ``--states uncached`` for it.

Run it::

    python -m tests.benchmark.hook_latency <project> --runs 5
    python -m tests.benchmark.hook_latency <project> --tasks <tasks.json> --task <id> \
        --label <name> --json --out results.json

``--tasks``/``--task`` take the prompt from a task-outcome ``tasks.json`` (as
in ``bench/task_outcome/``), so the call is timed on the prompt the task's
replay scores.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import statistics
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

DEFAULT_PROMPT = (
    "The error classifier misreads NVIDIA rate-limit errors as context overflow. Fix the "
    "classification so 429s from NVIDIA are treated as rate limits."
)
STATES = ("uncached", "miss", "cached")
# The Hermes plugin's default timeout (neuralmind/hermes_plugin DEFAULT_TIMEOUT).
PLUGIN_TIMEOUT = 8.0
# How long a sample may run before it is recorded as stopped.
SAMPLE_TIMEOUT = 120.0


def _child(python: str, *args: str, env: dict[str, str], stdin: str = "") -> str:
    done = subprocess.run(
        [python, "-P", *args],
        input=stdin,
        capture_output=True,
        text=True,
        timeout=SAMPLE_TIMEOUT,
        env=env,
        check=False,
    )
    return done.stdout


def _identity(python: str, env: dict[str, str]) -> dict[str, Any]:
    """The NeuralMind the hook runs: its version, and its checkout's commit if it is one."""
    out = _child(
        python,
        "-c",
        "import json, neuralmind; print(json.dumps({'version': neuralmind.__version__, "
        "'module': neuralmind.__file__}))",
        env=env,
    )
    try:
        found = json.loads(out)
    except ValueError:
        return {}
    # The commit, not the path: a result is committed, and a path is this machine's.
    package = str(Path(found["module"]).parent)
    commit = subprocess.run(
        ["git", "-C", package, "rev-parse", "--short", "HEAD"],
        capture_output=True,
        text=True,
        check=False,
    ).stdout.strip()
    changed = subprocess.run(
        ["git", "-C", package, "status", "--porcelain", "--untracked-files=no", "--", "."],
        capture_output=True,
        text=True,
        check=False,
    ).stdout.strip()
    # Uncommitted changes to the package: the commit alone doesn't say what ran.
    return {
        "version": found["version"],
        "commit": (commit + "-dirty" if changed else commit) or None,
    }


def _cache_files(project: Path) -> tuple[Path, Path]:
    state = project / ".neuralmind"
    return state / "graph_cache.marshal", state / "graph_cache.lock"


def _wait_for_warmer(project: Path, deadline: float = SAMPLE_TIMEOUT) -> None:
    """Wait until no background warmer holds the project's cache lock."""
    from neuralmind import graph_cache

    _, lock = _cache_files(project)
    if not lock.exists():
        return
    end = time.monotonic() + deadline
    while time.monotonic() < end:
        fd = os.open(lock, os.O_RDWR)
        try:
            if graph_cache._try_lock(fd):
                return
        finally:
            os.close(fd)  # closing releases a lock taken here
        time.sleep(0.2)


def _sample(python: str, payload: str, env: dict[str, str]) -> tuple[float, str]:
    """One hook call: seconds, and the SHA-256 of the context it returned."""
    start = time.perf_counter()
    out = _child(python, "-m", "neuralmind", "_hook", "prompt-submit", env=env, stdin=payload)
    seconds = time.perf_counter() - start
    try:
        context = json.loads(out)["hookSpecificOutput"]["additionalContext"]
    except (ValueError, KeyError, TypeError):
        context = ""
    return seconds, hashlib.sha256(context.encode("utf-8")).hexdigest()


def run(
    project: Path,
    *,
    prompt: str = DEFAULT_PROMPT,
    runs: int = 5,
    states: tuple[str, ...] = STATES,
    python: str = sys.executable,
    label: str | None = None,
) -> dict[str, Any]:
    project = project.resolve()
    payload = json.dumps({"cwd": str(project), "session_id": "hook-latency", "prompt": prompt})
    base_env = dict(os.environ, NEURALMIND_NO_LEARN="1")
    base_env.pop("NEURALMIND_GRAPH_CACHE", None)
    cache, _ = _cache_files(project)
    report: dict[str, Any] = {
        "project": label or project.name,
        "machine": {
            "platform": platform.platform(),
            "processor": platform.processor() or platform.machine(),
            "cpus": os.cpu_count(),
            "load_average": _load_average(),
        },
        "neuralmind": _identity(python, base_env),
        "prompt": prompt,
        "plugin_timeout_s": PLUGIN_TIMEOUT,
        "states": [],
    }
    blocks: set[str] = set()
    for state in states:
        env = dict(base_env)
        if state == "uncached":
            env["NEURALMIND_GRAPH_CACHE"] = "0"
        seconds: list[float] = []
        for _ in range(runs):
            _wait_for_warmer(project)
            if state == "miss":
                cache.unlink(missing_ok=True)
            elif state == "cached" and not cache.exists():
                _sample(python, payload, base_env)  # writes it; not counted
                _wait_for_warmer(project)
            took, block = _sample(python, payload, env)
            seconds.append(took)
            blocks.add(block)
        report["states"].append(
            {
                "state": state,
                "runs": runs,
                "mean_s": round(statistics.mean(seconds), 2),
                "min_s": round(min(seconds), 2),
                "max_s": round(max(seconds), 2),
                "within_plugin_timeout": sum(s < PLUGIN_TIMEOUT for s in seconds),
                "samples_s": [round(s, 2) for s in seconds],
            }
        )
    _wait_for_warmer(project)
    # One block for every call: the cache changes how fast, never what.
    report["block_sha256"] = sorted(blocks)
    # Read last, so the cache's size is there once a run has written it.
    report["index"] = _index_shape(project)
    return report


def _index_shape(project: Path) -> dict[str, Any]:
    state = project / ".neuralmind"
    shape: dict[str, Any] = {}
    for name in ("graph.json", "index_ir.json", "graph_cache.marshal"):
        try:
            shape[f"{name}_mb"] = round((state / name).stat().st_size / 1e6)
        except OSError:
            pass
    try:
        with (state / "graph.json").open(encoding="utf-8") as fh:
            graph = json.load(fh)
        shape["nodes"] = len(graph.get("nodes", []))
        shape["edges"] = len(graph.get("edges", graph.get("links", [])))
    except (OSError, ValueError):
        pass
    return shape


def _load_average() -> float | None:
    try:
        return round(os.getloadavg()[0], 1)
    except (AttributeError, OSError):
        return None


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("project", type=Path, help="a project with a built index")
    parser.add_argument("--prompt", default=DEFAULT_PROMPT)
    parser.add_argument("--tasks", type=Path, help="a task-outcome tasks.json to take it from")
    parser.add_argument("--task", help="the task id in --tasks")
    parser.add_argument("--label", help="the project's name in the report")
    parser.add_argument("--runs", type=int, default=5)
    parser.add_argument("--states", default=",".join(STATES), help="comma-separated")
    parser.add_argument("--python", default=sys.executable, help="interpreter to run the hook")
    parser.add_argument("--json", action="store_true", help="emit the raw report")
    parser.add_argument("--out", type=Path, help="also write the report here")
    args = parser.parse_args()

    states = tuple(s for s in args.states.split(",") if s)
    unknown = set(states) - set(STATES)
    if unknown:
        parser.error(f"unknown state(s): {', '.join(sorted(unknown))}")
    prompt = args.prompt
    if args.tasks or args.task:
        if not (args.tasks and args.task):
            parser.error("--tasks and --task go together")
        tasks = json.loads(args.tasks.read_text(encoding="utf-8"))
        tasks = tasks.get("tasks", tasks) if isinstance(tasks, dict) else tasks
        match = [t for t in tasks if t.get("id") == args.task]
        if not match:
            parser.error(f"no task {args.task!r} in {args.tasks}")
        prompt = match[0]["prompt"]
    report = run(
        args.project,
        prompt=prompt,
        runs=args.runs,
        states=states,
        python=args.python,
        label=args.label,
    )
    if args.out:
        args.out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    if args.json:
        print(json.dumps(report, indent=2))
        return
    shape = report["index"]
    print(
        f"prompt-submit hook — {report['project']}: {shape.get('nodes', '?'):,} nodes, "
        f"{shape.get('edges', '?'):,} edges; NeuralMind {report['neuralmind'].get('version')}\n"
    )
    print(f"{'state':<10}{'mean (s)':>10}{'min (s)':>10}{'max (s)':>10}{'< 8 s':>8}")
    for row in report["states"]:
        print(
            f"{row['state']:<10}{row['mean_s']:>10.2f}{row['min_s']:>10.2f}{row['max_s']:>10.2f}"
            f"{row['within_plugin_timeout']:>5}/{row['runs']}"
        )
    print(f"\nblock SHA-256: {', '.join(h[:12] for h in report['block_sha256'])}")


if __name__ == "__main__":
    main()
