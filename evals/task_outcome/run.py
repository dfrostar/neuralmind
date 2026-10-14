"""Run each task with the same agent, with and without NeuralMind.

    python -m evals.task_outcome.run --tasks evals/task_outcome/tasks.json \\
        --out bench/task_outcome/pilot --model <model-id> --seeds 3 \\
        --tool-venv <venv with neuralmind==X> --test-python <venv>/bin/python \\
        --work-dir <scratch> [--task ID ...] [--dry-run]

Two arms, identical except for NeuralMind:

``baseline``
    Claude Code headless (``claude -p``), project settings only, no MCP
    servers, ``NEURALMIND_BYPASS=1``, and no ``neuralmind`` on ``PATH``.
``neuralmind``
    The same, plus what a user gets from ``neuralmind build`` and
    ``neuralmind install-hooks`` in the project, and ``neuralmind-mcp``
    registered as an MCP server. The agent is not told to use it.

Both arms get the same prompt, model, tool allowlist and budget cap, and only
the MCP servers this script passes (``--strict-mcp-config``), so the user's own
settings, hooks and connectors stay out. The index build happens before the
agent's clock starts; its time is recorded separately.

After the agent stops, the fix's own tests are laid over the workspace and run:
a task is solved when every FAIL_TO_PASS test and every PASS_TO_PASS test
passes. Each run appends one JSON line to ``<out>/runs.jsonl``; a rerun skips
(task, arm, seed) triples already recorded.
"""

from __future__ import annotations

import argparse
import json
import os
import random
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from evals.task_outcome import harness

HARNESS_VERSION = 1
ARMS = ("baseline", "neuralmind")
BASE_TOOLS = [
    "Read",
    "Edit",
    "Write",
    "Glob",
    "Grep",
    "Bash(python -m pytest:*)",
    "Bash(git diff:*)",
    "Bash(git status:*)",
    "Bash(ls:*)",
]
EDIT_TOOLS = {"Edit", "Write", "MultiEdit", "NotebookEdit"}
EXPLORE_TOOLS = {"Read", "Grep", "Glob", "Bash"}

PROMPT = """{symptom}

You are working in a checkout of the NeuralMind repository. Find the cause and \
fix it in the source code. Don't add or change tests: the fix is judged by tests \
you can't see. You can run the existing tests with `python -m pytest <path>`. \
Stop when the fix is done."""


def _arm_env(arm: str, tool_venv: Path, test_python: str) -> dict[str, str]:
    env = {k: v for k, v in os.environ.items() if not k.startswith("NEURALMIND_")}
    env.pop("PYTHONPATH", None)
    path = [str(Path(test_python).parent)]
    if arm == "neuralmind":
        path.append(str(tool_venv / "bin"))
    else:
        env["NEURALMIND_BYPASS"] = "1"
    env["PATH"] = os.pathsep.join(path + [os.environ.get("PATH", "")])
    return env


def _prepare(task: dict, arm: str, ws: Path, tool_venv: Path, env: dict) -> dict:
    """Snapshot the base commit; for the neuralmind arm, build and wire it up."""
    harness.snapshot(task["base_commit"], ws)
    exclude = ws / ".git" / "info" / "exclude"
    exclude.write_text(exclude.read_text() + "\n.claude/\n.neuralmind/\n.bench-*\n")
    mcp_servers: dict = {}
    build_seconds = 0.0
    if arm == "neuralmind":
        nm = str(tool_venv / "bin" / "neuralmind")
        t0 = time.monotonic()
        subprocess.run([nm, "build", str(ws)], cwd=ws, env=env, capture_output=True, check=True)
        build_seconds = round(time.monotonic() - t0, 1)
        subprocess.run(
            [nm, "install-hooks", str(ws)], cwd=ws, env=env, capture_output=True, check=True
        )
        mcp_servers = {
            "neuralmind": {"command": str(tool_venv / "bin" / "neuralmind-mcp"), "args": []}
        }
    mcp_file = ws / ".bench-mcp.json"
    mcp_file.write_text(json.dumps({"mcpServers": mcp_servers}))
    return {"mcp_file": mcp_file, "build_seconds": build_seconds}


def claude_command(prompt: str, arm: str, model: str, mcp_file: Path, budget: float) -> list[str]:
    tools = BASE_TOOLS + (["mcp__neuralmind"] if arm == "neuralmind" else [])
    return [
        "claude",
        "-p",
        prompt,
        "--model",
        model,
        "--output-format",
        "stream-json",
        "--verbose",
        "--setting-sources",
        "project",
        "--strict-mcp-config",
        "--mcp-config",
        str(mcp_file),
        "--permission-mode",
        "acceptEdits",
        "--allowedTools",
        *tools,
        "--max-budget-usd",
        str(budget),
        "--no-session-persistence",
    ]


def parse_stream(lines: list[str]) -> dict:
    """Usage from the final ``result`` event, tool use from the assistant turns."""
    result: dict = {}
    tool_counts: dict[str, int] = {}
    explore_before_edit = 0
    edited = False
    for line in lines:
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if event.get("type") == "result":
            result = event
        if event.get("type") != "assistant":
            continue
        for block in event.get("message", {}).get("content", []) or []:
            if not isinstance(block, dict) or block.get("type") != "tool_use":
                continue
            name = block.get("name", "")
            tool_counts[name] = tool_counts.get(name, 0) + 1
            if name in EDIT_TOOLS:
                edited = True
            elif not edited and (name in EXPLORE_TOOLS or name.startswith("mcp__")):
                explore_before_edit += 1
    usage = result.get("usage", {}) or {}
    return {
        "cost_usd": result.get("total_cost_usd"),
        "input_tokens": usage.get("input_tokens"),
        "output_tokens": usage.get("output_tokens"),
        "cache_creation_input_tokens": usage.get("cache_creation_input_tokens"),
        "cache_read_input_tokens": usage.get("cache_read_input_tokens"),
        "num_turns": result.get("num_turns"),
        "duration_ms": result.get("duration_ms"),
        "is_error": result.get("is_error"),
        "subtype": result.get("subtype"),
        "tool_counts": tool_counts,
        "explore_calls_before_first_edit": explore_before_edit,
        "edited": edited,
    }


def judge(task: dict, ws: Path, test_python: str) -> dict:
    harness.overlay(task["fix_commit"], task["test_files"], ws)
    outcomes = harness.run_tests(ws, task["run_files"], test_python)
    f2p_ok = [t for t in task["fail_to_pass"] if outcomes.get(t) == "passed"]
    p2p_bad = [t for t in task["pass_to_pass"] if outcomes.get(t) != "passed"]
    return {
        "solved": len(f2p_ok) == len(task["fail_to_pass"]) and not p2p_bad,
        "f2p_passed": len(f2p_ok),
        "f2p_total": len(task["fail_to_pass"]),
        "p2p_failed": len(p2p_bad),
    }


def run_one(task: dict, arm: str, seed: int, args: argparse.Namespace) -> dict:
    ws = args.work_dir / f"{task['id']}-{arm}-s{seed}-{int(time.time())}"
    env = _arm_env(arm, args.tool_venv, args.test_python)
    prep = _prepare(task, arm, ws, args.tool_venv, env)
    cmd = claude_command(
        PROMPT.format(symptom=task["prompt"].strip()),
        arm,
        args.model,
        prep["mcp_file"],
        args.budget,
    )
    started = datetime.now(timezone.utc).isoformat(timespec="seconds")
    transcript = args.out / "transcripts" / f"{task['id']}-{arm}-s{seed}.jsonl"
    transcript.parent.mkdir(parents=True, exist_ok=True)
    try:
        proc = subprocess.run(
            cmd, cwd=ws, env=env, capture_output=True, text=True, timeout=args.timeout
        )
        stdout, timed_out = proc.stdout, False
    except subprocess.TimeoutExpired as exc:
        stdout = exc.stdout.decode() if isinstance(exc.stdout, bytes) else (exc.stdout or "")
        timed_out = True
    transcript.write_text(stdout)
    agent = parse_stream(stdout.splitlines())
    changed = subprocess.run(
        ["git", "diff", "--name-only"], cwd=ws, capture_output=True, text=True
    ).stdout.split()
    verdict = judge(task, ws, args.test_python)
    if not args.keep_workspaces:
        shutil.rmtree(ws, ignore_errors=True)
    return {
        "task": task["id"],
        "arm": arm,
        "seed": seed,
        "model": args.model,
        "harness_version": HARNESS_VERSION,
        "started_at": started,
        "timed_out": timed_out,
        "build_seconds": prep["build_seconds"],
        "changed_files": changed,
        "gold_touched": bool(set(changed) & set(task["gold_files"])),
        **agent,
        **verdict,
    }


def plan(tasks: list[dict], arms: tuple[str, ...], seeds: int, order_seed: int) -> list[tuple]:
    """Every (task, arm, seed) triple, shuffled so neither arm runs first in bulk."""
    triples = [(t["id"], a, s) for t in tasks for s in range(seeds) for a in arms]
    random.Random(order_seed).shuffle(triples)
    return triples


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--tasks", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--model", required=True)
    ap.add_argument("--seeds", type=int, default=3)
    ap.add_argument("--arms", default=",".join(ARMS))
    ap.add_argument("--task", action="append", help="run only these task ids")
    ap.add_argument("--tool-venv", type=Path, required=True)
    ap.add_argument("--test-python", required=True)
    ap.add_argument("--work-dir", type=Path, required=True)
    ap.add_argument(
        "--budget", type=float, default=2.0, help="max USD per run (claude --max-budget-usd)"
    )
    ap.add_argument("--timeout", type=int, default=1800, help="seconds per run")
    ap.add_argument("--order-seed", type=int, default=20261014)
    ap.add_argument("--keep-workspaces", action="store_true")
    ap.add_argument(
        "--dry-run", action="store_true", help="print the plan and one command, run nothing"
    )
    args = ap.parse_args(argv)

    tasks = json.loads(args.tasks.read_text())
    if args.task:
        tasks = [t for t in tasks if t["id"] in set(args.task)]
    missing = [t["id"] for t in tasks if not t.get("prompt", "").strip()]
    if missing:
        print(f"error: tasks without a prompt: {', '.join(missing)}", file=sys.stderr)
        return 2
    arms = tuple(a for a in args.arms.split(",") if a)
    by_id = {t["id"]: t for t in tasks}
    triples = plan(tasks, arms, args.seeds, args.order_seed)

    args.out.mkdir(parents=True, exist_ok=True)
    runs_file = args.out / "runs.jsonl"
    done = set()
    if runs_file.is_file():
        for line in runs_file.read_text().splitlines():
            r = json.loads(line)
            done.add((r["task"], r["arm"], r["seed"]))
    todo = [t for t in triples if t not in done]
    print(f"{len(triples)} run(s) planned, {len(todo)} to do")

    if args.dry_run:
        if todo:
            tid, arm, _ = todo[0]
            cmd = claude_command(
                PROMPT.format(symptom=by_id[tid]["prompt"].strip()),
                arm,
                args.model,
                Path("<ws>/.bench-mcp.json"),
                args.budget,
            )
            print(" ".join(cmd[:2] + ["<prompt>"] + cmd[3:]))
        return 0

    args.work_dir.mkdir(parents=True, exist_ok=True)
    for i, (tid, arm, seed) in enumerate(todo, 1):
        record = run_one(by_id[tid], arm, seed, args)
        with runs_file.open("a") as fh:
            fh.write(json.dumps(record) + "\n")
        print(
            f"[{i}/{len(todo)}] {tid} {arm} s{seed}: solved={record['solved']} "
            f"cost=${record['cost_usd']} turns={record['num_turns']}",
            flush=True,
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
