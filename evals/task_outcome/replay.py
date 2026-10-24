# SPDX-License-Identifier: MIT
"""What the prompt hook shows the agent for each benchmark task, scored offline.

    python -m evals.task_outcome.replay --work-dir <scratch> --out <dir> [--reuse] [--check]

The task-outcome benchmark (``run.py``) costs an agent run per task and arm.
This replays only NeuralMind's half of a run's first turn, with no agent and no
API cost: for each task in ``tasks.json`` it exports the fix's parent commit,
builds the index with the ``neuralmind`` on ``PATH``, and pipes the task's
prompt into ``neuralmind _hook prompt-submit``, the command Claude Code runs on
``UserPromptSubmit``. The block it prints is scored against the fix itself:

* ``named``: a gold file (one the fix changed) is among the files listed.
* ``first``: a gold file is the first file listed.
* ``excerpt_shown`` / ``excerpt_on_gold``: the block quotes code (only when one
  file clearly leads; see ``neuralmind.prompt_recall``) and it is a gold file's.
* ``excerpt_on_fix``: the quoted lines overlap lines the fix changed.

``--check`` fails (exit 1) when a count falls below ``FLOORS``. The tasks are
the pilot's 20, so the floors guard a regression on prompts the pilot ran; the
excerpt's gate was set on these same prompts, so its precision here is a
ceiling, not an estimate. The confirmatory run's new tasks are the estimate.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

from evals.task_outcome import harness
from evals.task_outcome.run import PROMPT

TASKS = Path(__file__).with_name("tasks.json")

# Counts out of 20, set under what the change that added them measured so build
# to build variation doesn't fail the job: two fresh builds of the same commits
# differed by one task's "connected" list (named 17 vs 18). Raise them with the
# measurement that justifies it.
FLOORS = {
    "named": 15,  # measured 17 on a fresh build (v4.18.1 + excerpt, 2026-10-21)
    "first": 9,  # measured 10
    "excerpt_on_gold_share": 0.7,  # measured 7 of 9
}

_LISTED = re.compile(r"^- ([^:\n]+?)(?::|$)", re.MULTILINE)
_EXCERPT = re.compile(r"^Most matches are in (.+?)\. Its best match, L(\d+)-L(\d+)", re.MULTILINE)
_HUNK = re.compile(r"^@@ -(\d+)(?:,(\d+))? ", re.MULTILINE)


def fix_lines(task: dict) -> dict[str, list[tuple[int, int]]]:
    """Line ranges each gold file's fix changed, in the parent commit's numbering."""
    ranges: dict[str, list[tuple[int, int]]] = {}
    for path in task["gold_files"]:
        diff = harness.git(
            "diff", "-U0", task["base_commit"], task["fix_commit"], "--", path
        ).decode()
        for m in _HUNK.finditer(diff):
            start, count = int(m.group(1)), int(m.group(2) or "1")
            # A pure insertion (count 0) sits after line `start`.
            ranges.setdefault(path, []).append((start, start + max(count, 1) - 1))
    return ranges


def score(block: str, task: dict, changed: dict[str, list[tuple[int, int]]]) -> dict:
    """Score one hook block against the task's fix."""
    gold = set(task["gold_files"])
    listed = [p.strip() for p in _LISTED.findall(block)]
    excerpt = _EXCERPT.search(block)
    record = {
        "listed": listed,
        "named": bool(gold & set(listed)),
        "first": bool(listed) and listed[0] in gold,
        "excerpt_shown": bool(excerpt),
        "excerpt_on_gold": False,
        "excerpt_on_fix": False,
        "chars": len(block),
    }
    if excerpt:
        path, lo, hi = excerpt.group(1), int(excerpt.group(2)), int(excerpt.group(3))
        record["excerpt"] = [path, lo, hi]
        record["excerpt_on_gold"] = path in gold
        record["excerpt_on_fix"] = any(a <= hi and lo <= b for a, b in changed.get(path, []))
    return record


def hook_block(ws: Path, prompt: str, env: dict) -> str:
    payload = {
        "hook_event_name": "UserPromptSubmit",
        "prompt": prompt,
        "cwd": str(ws),
        "session_id": "replay",
    }
    proc = subprocess.run(
        ["neuralmind", "_hook", "prompt-submit"],
        cwd=ws,
        env=env,
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        check=True,
    )
    if not proc.stdout.strip():
        return ""
    return json.loads(proc.stdout)["hookSpecificOutput"]["additionalContext"]


def summarize(records: list[dict]) -> dict:
    shown = [r for r in records if r["excerpt_shown"]]
    on_gold = sum(r["excerpt_on_gold"] for r in shown)
    return {
        "tasks": len(records),
        "named": sum(r["named"] for r in records),
        "first": sum(r["first"] for r in records),
        "excerpt_shown": len(shown),
        "excerpt_on_gold": on_gold,
        "excerpt_on_fix": sum(r["excerpt_on_fix"] for r in shown),
        "excerpt_on_gold_share": round(on_gold / len(shown), 3) if shown else None,
        "median_chars": sorted(r["chars"] for r in records)[len(records) // 2] if records else 0,
    }


def below_floors(summary: dict) -> list[str]:
    failures = []
    for key, floor in FLOORS.items():
        value = summary.get(key)
        # No excerpt shown at all is not a precision failure.
        if value is not None and value < floor:
            failures.append(f"{key} {value} < floor {floor}")
    return failures


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--tasks", type=Path, default=TASKS)
    ap.add_argument("--work-dir", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--reuse", action="store_true", help="keep a workspace's index if built")
    ap.add_argument("--check", action="store_true", help="exit 1 below FLOORS")
    args = ap.parse_args(argv)

    if not shutil.which("neuralmind"):
        print("error: `neuralmind` is not on PATH", file=sys.stderr)
        return 2
    version = subprocess.run(
        ["neuralmind", "--version"], capture_output=True, text=True, check=True
    ).stdout.strip()
    env = {k: v for k, v in os.environ.items() if not k.startswith("NEURALMIND_")}
    tasks = json.loads(args.tasks.read_text())
    records = []
    for task in tasks:
        ws = args.work_dir / task["id"]
        if not (args.reuse and (ws / ".neuralmind").is_dir()):
            shutil.rmtree(ws, ignore_errors=True)
            harness.snapshot(task["base_commit"], ws)
            t0 = time.monotonic()
            subprocess.run(
                ["neuralmind", "build", str(ws)], cwd=ws, env=env, capture_output=True, check=True
            )
            print(f"{task['id']}: built in {time.monotonic() - t0:.0f}s", flush=True)
        block = hook_block(ws, PROMPT.format(symptom=task["prompt"].strip()), env)
        record = {"task": task["id"], "gold": task["gold_files"]}
        record.update(score(block, task, fix_lines(task)))
        records.append(record)
        (args.out / "blocks").mkdir(parents=True, exist_ok=True)
        (args.out / "blocks" / f"{task['id']}.md").write_text(block)

    summary = {"neuralmind_version": version, **summarize(records)}
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "replay-results.json").write_text(
        json.dumps({"summary": summary, "tasks": records}, indent=2) + "\n"
    )
    print(json.dumps(summary, indent=2))
    if args.check:
        failures = below_floors(summary)
        for failure in failures:
            print(f"FAIL: {failure}", file=sys.stderr)
        return 1 if failures else 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
