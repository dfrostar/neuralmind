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

``--agent hermes`` runs the same tasks with Hermes-Agent instead (``hermes chat
-Q --format stream-json``), on whatever model Hermes's own config selects;
``--model`` names the model every run must have used, and a run on any other
is a harness failure. Each session gets only Hermes's file and terminal tools,
no MCP servers (``no_mcp``), and no memory provider, context files or
preloaded skills (``--ignore-rules``), so one run can't recall another. In the
``neuralmind`` arm, NeuralMind reaches the agent only through the Hermes
plugin, which serves a session's directory once it has an index; the
``baseline`` arm's workspace has none. A local model has no dollar cost, so
these runs record tokens instead.

After the agent stops, the fix's own tests are laid over the workspace and run:
a task is solved when every FAIL_TO_PASS test and every PASS_TO_PASS test
passes. Each run appends one JSON line to ``<out>/runs.jsonl``; a rerun skips
(task, arm, seed) triples already recorded.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import random
import shutil
import signal
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from evals.task_outcome import harness

HARNESS_VERSION = 2
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
AGENTS = ("claude", "hermes")
HERMES_TOOLSETS = "file,terminal,no_mcp"
HERMES_STATE_DB = Path.home() / ".hermes" / "state.db"
HERMES_PLUGIN_CONFIG = Path.home() / ".hermes" / "plugins" / "neuralmind" / "config.json"
# Claude Code's tool names, then Hermes's.
EDIT_TOOLS = {"Edit", "Write", "MultiEdit", "NotebookEdit", "write_file", "patch"}
EXPLORE_TOOLS = {"Read", "Grep", "Glob", "Bash", "read_file", "search_files", "terminal"}

PROMPT = """{symptom}

You are working in a checkout of the NeuralMind repository. Find the cause and \
fix it in the source code. Don't add or change tests: the fix is judged by tests \
you can't see. You can run the existing tests with `python -m pytest <path>`. \
Stop when the fix is done."""


class RunAbortedError(RuntimeError):
    """The harness, not the agent, failed: nothing is recorded, a rerun retries."""


def _clean_path(host_path: str) -> list[str]:
    """The host's ``PATH`` minus every directory holding a ``neuralmind`` executable.

    A NeuralMind install already on the host (``~/.local/bin`` here) would
    otherwise reach the baseline arm, and in the other arm could shadow the
    pinned release the hooks are meant to call.
    """
    keep = []
    for d in host_path.split(os.pathsep):
        if d and not any(
            os.access(Path(d) / name, os.X_OK) for name in ("neuralmind", "neuralmind-mcp")
        ):
            keep.append(d)
    return keep


def _arm_env(arm: str, tool_venv: Path, test_python: str) -> dict[str, str]:
    env = {k: v for k, v in os.environ.items() if not k.startswith("NEURALMIND_")}
    env.pop("PYTHONPATH", None)
    path = [str(Path(test_python).parent)]
    if arm == "neuralmind":
        path.append(str(tool_venv / "bin"))
    else:
        env["NEURALMIND_BYPASS"] = "1"
    env["PATH"] = os.pathsep.join(path + _clean_path(os.environ.get("PATH", "")))
    found = shutil.which("neuralmind", path=env["PATH"])
    expected = str(tool_venv / "bin" / "neuralmind") if arm == "neuralmind" else None
    if found != expected:
        raise RunAbortedError(f"{arm} arm: `neuralmind` resolves to {found}, expected {expected}")
    return env


def _prepare(
    task: dict, arm: str, ws: Path, tool_venv: Path, env: dict, agent: str = "claude"
) -> dict:
    """Snapshot the base commit; for the neuralmind arm, build and wire it up.

    Hermes needs only the index: its NeuralMind plugin serves any session
    directory that has one.
    """
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
    if arm == "neuralmind" and agent == "claude":
        nm = str(tool_venv / "bin" / "neuralmind")
        subprocess.run(
            [nm, "install-hooks", str(ws)], cwd=ws, env=env, capture_output=True, check=True
        )
        mcp_servers = {
            "neuralmind": {"command": str(tool_venv / "bin" / "neuralmind-mcp"), "args": []}
        }
    mcp_file = ws / ".bench-mcp.json"
    mcp_file.write_text(json.dumps({"mcpServers": mcp_servers}))
    return {"mcp_file": mcp_file, "build_seconds": build_seconds}


def claude_command(
    claude_bin: str, prompt: str, arm: str, model: str, mcp_file: Path, budget: float
) -> list[str]:
    tools = BASE_TOOLS + (["mcp__neuralmind"] if arm == "neuralmind" else [])
    return [
        claude_bin,
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
        "terminal_reason": result.get("terminal_reason"),
        "tool_counts": tool_counts,
        "explore_calls_before_first_edit": explore_before_edit,
        "edited": edited,
    }


def hermes_command(hermes_bin: str, prompt_file: Path, max_turns: int) -> list[str]:
    return [
        hermes_bin,
        "chat",
        "-Q",
        "--format",
        "stream-json",
        "--ignore-rules",
        "--source",
        "tool",
        "-t",
        HERMES_TOOLSETS,
        "--max-turns",
        str(max_turns),
        "--query-file",
        str(prompt_file),
    ]


def parse_hermes_stream(lines: list[str]) -> dict:
    """Usage from Hermes's final ``result`` event, tool use from its ``tool_use`` events."""
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
        if event.get("type") != "tool_use":
            continue
        name = event.get("name", "")
        tool_counts[name] = tool_counts.get(name, 0) + 1
        if name in EDIT_TOOLS:
            edited = True
        elif not edited and name in EXPLORE_TOOLS:
            explore_before_edit += 1
    tokens = result.get("tokens", {}) or {}
    exit_code = result.get("exit_code")
    return {
        "cost_usd": None,
        "input_tokens": tokens.get("input"),
        "output_tokens": tokens.get("output"),
        "total_tokens": tokens.get("total"),
        "cache_creation_input_tokens": tokens.get("cache_write"),
        "cache_read_input_tokens": tokens.get("cache_read"),
        "num_turns": None,
        "duration_ms": result.get("duration_ms"),
        "is_error": None if not result else exit_code != 0,
        "subtype": None if not result else ("success" if exit_code == 0 else "error"),
        "terminal_reason": None,
        "session_id": result.get("session_id"),
        "tool_counts": tool_counts,
        "explore_calls_before_first_edit": explore_before_edit,
        "edited": edited,
    }


def _state_db_rows(state_db: Path, sql: str, params: tuple) -> list[tuple]:
    if not state_db.is_file():
        return []
    import sqlite3

    db = sqlite3.connect(f"file:{state_db}?mode=ro", uri=True)
    try:
        return db.execute(sql, params).fetchall()
    finally:
        db.close()


def hermes_session(session_id: str | None, state_db: Path = HERMES_STATE_DB) -> dict:
    """The model, API calls and tokens Hermes recorded for a session, read-only."""
    if not session_id:
        return {}
    rows = _state_db_rows(
        state_db,
        "SELECT model, api_call_count, billing_base_url, input_tokens, output_tokens "
        "FROM sessions WHERE id = ?",
        (session_id,),
    )
    if not rows:
        return {}
    model, calls, base_url, tokens_in, tokens_out = rows[0]
    return {
        "model": model,
        "api_calls": calls,
        "base_url": base_url,
        "input_tokens": tokens_in,
        "output_tokens": tokens_out,
    }


def hermes_session_in(ws: Path, state_db: Path = HERMES_STATE_DB) -> str | None:
    """The newest Hermes session started in ``ws``.

    A run cut off by the timeout prints no ``result`` event, so its session id
    comes from here. Hermes records the resolved directory.
    """
    rows = _state_db_rows(
        state_db,
        "SELECT id FROM sessions WHERE cwd = ? ORDER BY started_at DESC LIMIT 1",
        (os.path.realpath(ws),),
    )
    return rows[0][0] if rows else None


def _works_in(pid_dir: Path, root: str) -> bool:
    """Is the process working in ``root``, or was it started there?

    The agent's test runs change into pytest's temporary directories, outside
    the workspace, so the working directory alone misses them. The ``PWD`` the
    shell that started a command exported, which its children inherit, still
    names the workspace.
    """
    try:
        dirs = [os.readlink(pid_dir / "cwd")]
    except OSError:
        return False
    try:
        env = (pid_dir / "environ").read_bytes().split(b"\0")
    except OSError:
        env = []
    dirs += [v[4:].decode(errors="replace") for v in env if v.startswith(b"PWD=")]
    return any(d == root or d.startswith(root + os.sep) for d in dirs)


def stop_workspace_processes(ws: Path) -> int:
    """Terminate every process working in ``ws``, or started there (Linux).

    The agent's commands run in the Hermes gateway, not under this script, and
    a command it left in the background would go on changing the workspace
    while the tests judge it. When one finishes, Hermes also wakes the session
    for another turn. Returns how many were stopped.
    """
    proc = Path("/proc")
    if not proc.is_dir():
        return 0
    root = os.path.realpath(ws)
    stopped = 0
    for entry in proc.iterdir():
        if not entry.name.isdigit() or int(entry.name) == os.getpid():
            continue
        if _works_in(entry, root):
            try:
                os.kill(int(entry.name), signal.SIGTERM)
                stopped += 1
            except OSError:
                pass
    return stopped


def wait_hermes_idle(
    session_id: str | None,
    state_db: Path = HERMES_STATE_DB,
    quiet: float = 30.0,
    limit: float = 3600.0,
    poll: float = 2.0,
) -> float | None:
    """Wait until Hermes has no work left for the session; seconds waited, None at ``limit``.

    The Hermes client returns, or is killed at the timeout, while the gateway
    may still be running the session: a killed client leaves its turn going,
    and a finished background command queues a new one. Idle means no queued
    or running turn (every admission ``terminal``) and no activity for
    ``quiet`` seconds.
    """
    if not session_id:
        return 0.0
    start = time.monotonic()
    while True:
        pending = _state_db_rows(
            state_db,
            "SELECT count(*) FROM session_admissions "
            "WHERE target_session_id = ? AND status != 'terminal'",
            (session_id,),
        )
        last = _state_db_rows(
            state_db, "SELECT last_activity_at FROM sessions WHERE id = ?", (session_id,)
        )
        busy = bool(pending and pending[0][0])
        recent = bool(last and last[0][0] and time.time() - last[0][0] < quiet)
        if not busy and not recent:
            return round(time.monotonic() - start, 1)
        if time.monotonic() - start > limit:
            return None
        time.sleep(poll)


def settle_workspace(
    ws: Path, session_id: str | None, rounds: int = 5, settle: float = 10.0
) -> tuple[int, float | None, bool]:
    """Stop what the agent left running and wait out the turns that wake, until nothing is left.

    Returns the processes stopped, the seconds waited for Hermes (None at the
    hour limit), and whether the workspace settled: a scan found nothing and
    the session was already idle, so no turn ran since the scan before it. A
    turn that runs during a wait can start another command, so one wait is
    never the last step. Hermes notices a stopped process a moment later and
    wakes the session, so a scan that stopped any waits ``settle`` seconds first.
    """
    stopped, waited = 0, 0.0
    for _ in range(rounds):
        n = stop_workspace_processes(ws)
        stopped += n
        if n:
            time.sleep(settle)
        more = wait_hermes_idle(session_id)
        if more is None:
            return stopped, None, False
        waited += more
        if not n and not more:
            return stopped, waited, True
    return stopped, waited, False


def harness_failure(agent: dict, timed_out: bool) -> bool:
    """Did Claude Code fail before or instead of the agent, rather than the agent fail?

    No final ``result`` event is one way. The other is a ``result`` event that
    ends on an API error: a logged-out CLI reports "Not logged in" that way,
    with ``subtype`` "success" and no model call, so the event alone is no proof
    the agent ran.
    """
    if timed_out:
        return False
    return agent["subtype"] is None or agent.get("terminal_reason") == "api_error"


def hook_activity(ws: Path) -> dict:
    """Manipulation check: did NeuralMind's hooks run inside this session?

    Claude Code's event stream shows only the SessionStart hook, so the
    evidence is NeuralMind's own session recap, which its prompt and edit
    hooks append to while the session runs.
    """
    prompts = edits = 0
    for recap in (ws / ".neuralmind" / "recaps").glob("*.jsonl"):
        for line in recap.read_text().splitlines():
            kind = json.loads(line).get("kind") if line.strip() else None
            prompts += kind == "prompt"
            edits += kind == "edit"
    return {"hook_prompts_recorded": prompts, "hook_edits_recorded": edits}


def neuralmind_missing(arm: str, hooks: dict) -> bool:
    """The manipulation check: did a ``neuralmind``-arm run go without NeuralMind?

    No prompt recorded in the workspace means NeuralMind never reached the
    session (a plugin pinned to another project, say), so the run would measure
    the baseline under the other arm's name. That's a harness failure.
    """
    return arm == "neuralmind" and not hooks.get("hook_prompts_recorded")


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
    prep = _prepare(task, arm, ws, args.tool_venv, env, args.agent)
    prompt = PROMPT.format(symptom=task["prompt"].strip())
    if args.agent == "hermes":
        # Outside the workspace, so the agent's file tools don't list it.
        prompt_file = ws.parent / f"{ws.name}.prompt.txt"
        prompt_file.write_text(prompt)
        cmd = hermes_command(args.agent_bin, prompt_file, args.max_turns)
    else:
        cmd = claude_command(args.agent_bin, prompt, arm, args.model, prep["mcp_file"], args.budget)
    started = datetime.now(timezone.utc).isoformat(timespec="seconds")
    transcript = args.out / "transcripts" / f"{task['id']}-{arm}-s{seed}.jsonl"
    transcript.parent.mkdir(parents=True, exist_ok=True)
    stderr = ""
    try:
        proc = subprocess.run(
            cmd, cwd=ws, env=env, capture_output=True, text=True, timeout=args.timeout
        )
        stdout, stderr, exit_code, timed_out = proc.stdout, proc.stderr, proc.returncode, False
    except subprocess.TimeoutExpired as exc:
        stdout = exc.stdout.decode() if isinstance(exc.stdout, bytes) else (exc.stdout or "")
        exit_code, timed_out = None, True
    transcript.write_text(stdout)
    transcript_sha256 = hashlib.sha256(stdout.encode()).hexdigest()
    failure = ""
    if args.agent == "hermes":
        prompt_file.unlink(missing_ok=True)
        agent = parse_hermes_stream(stdout.splitlines())
        session_id = agent["session_id"] or hermes_session_in(ws)
        agent["session_id"] = session_id
        # Nothing may still be working in the workspace when the tests judge it.
        stopped, waited, settled = settle_workspace(ws, session_id)
        agent["background_processes_stopped"] = stopped
        agent["hermes_idle_wait_s"] = waited
        if waited is None:
            failure = "the session was still running in the Hermes gateway an hour later"
        elif not settled:
            failure = "commands kept starting in the workspace after five rounds of stopping them"
        session = hermes_session(session_id)
        agent["num_turns"] = session.get("api_calls")
        agent["hermes_model"] = session.get("model")
        agent["hermes_base_url"] = session.get("base_url")
        if agent["total_tokens"] is None and session.get("input_tokens") is not None:
            # Cut off before its result event: the session's own count so far.
            agent["input_tokens"] = session["input_tokens"]
            agent["output_tokens"] = session["output_tokens"]
            agent["total_tokens"] = session["input_tokens"] + (session["output_tokens"] or 0)
        if session and session.get("model") != args.model:
            # Hermes falls back to another provider when its own model fails:
            # that run measured some other model.
            failure = f"session ran on {session.get('model')!r}, not {args.model!r}"
    else:
        agent = parse_stream(stdout.splitlines())
    hooks = hook_activity(ws) if arm == "neuralmind" else {}
    if not failure and not harness_failure(agent, timed_out) and neuralmind_missing(arm, hooks):
        failure = "NeuralMind's prompt hook recorded nothing in the workspace"
    if harness_failure(agent, timed_out) or failure:
        # Authentication, model or CLI failure. That is the harness failing,
        # not the agent, so it must not become an outcome.
        shutil.rmtree(ws, ignore_errors=True)
        transcript.unlink(missing_ok=True)
        raise RunAbortedError(
            f"{task['id']} {arm} s{seed}: "
            + (
                failure
                or f"{args.agent} exited {exit_code} without an agent result "
                f"(terminal_reason={agent.get('terminal_reason')})"
            )
            + f"; stderr: {stderr.strip()[-500:]}"
        )
    changed = sorted(
        set(
            subprocess.run(
                ["git", "diff", "--name-only"], cwd=ws, capture_output=True, text=True
            ).stdout.split()
        )
        | set(
            subprocess.run(
                ["git", "ls-files", "--others", "--exclude-standard"],
                cwd=ws,
                capture_output=True,
                text=True,
            ).stdout.split()
        )
    )
    verdict = judge(task, ws, args.test_python)
    if not args.keep_workspaces:
        shutil.rmtree(ws, ignore_errors=True)
    return {
        "task": task["id"],
        "arm": arm,
        "seed": seed,
        "agent": args.agent,
        "model": args.model,
        **args.versions,
        "harness_version": HARNESS_VERSION,
        "budget_usd": args.budget if args.agent == "claude" else None,
        "max_turns": args.max_turns if args.agent == "hermes" else None,
        "started_at": started,
        "timed_out": timed_out,
        "exit_code": exit_code,
        "transcript_sha256": transcript_sha256,
        "build_seconds": prep["build_seconds"],
        "changed_files": changed,
        "gold_touched": bool(set(changed) & set(task["gold_files"])),
        **hooks,
        **agent,
        **verdict,
    }


def probe_versions(agent_bin: str, tool_venv: Path, agent: str = "claude") -> dict[str, str]:
    """The pinned binaries, recorded on every run so one file can't mix them.

    Under Hermes the hooks run with the plugin's own interpreter, not the tool
    venv, so its NeuralMind is recorded too.
    """

    def version(cmd: list[str]) -> str:
        return subprocess.run(cmd, capture_output=True, text=True, check=True).stdout.strip()

    versions = {
        "neuralmind_version": version([str(tool_venv / "bin" / "neuralmind"), "--version"]),
    }
    if agent == "hermes":
        versions["hermes_version"] = version([agent_bin, "--version"]).splitlines()[0]
        plugin_python = json.loads(HERMES_PLUGIN_CONFIG.read_text()).get("python") or "python3"
        versions["hermes_plugin_neuralmind_version"] = version(
            [plugin_python, "-P", "-m", "neuralmind", "--version"]
        )
    else:
        versions["claude_code_version"] = version([agent_bin, "--version"])
    return versions


def hermes_plugin_pin(config: Path = HERMES_PLUGIN_CONFIG) -> str | None:
    """The project the Hermes plugin was pinned to at install, if any.

    The plugin serves a pinned project ahead of the session's directory, so a
    pinned plugin would hand every run another checkout's context.
    """
    return json.loads(config.read_text()).get("project") or None


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
    ap.add_argument("--agent", choices=AGENTS, default="claude")
    ap.add_argument(
        "--max-turns", type=int, default=60, help="tool-calling iterations per run (hermes)"
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
    # Resolved here, by full path: the arms' cleaned PATH can drop its directory.
    args.agent_bin = shutil.which(args.agent)
    if not args.agent_bin:
        print(f"error: `{args.agent}` is not on PATH", file=sys.stderr)
        return 2
    args.versions = probe_versions(args.agent_bin, args.tool_venv, args.agent)
    plugin_nm = args.versions.get("hermes_plugin_neuralmind_version")
    if plugin_nm and plugin_nm != args.versions["neuralmind_version"]:
        print(
            f"error: the Hermes plugin runs {plugin_nm}, the tool venv "
            f"{args.versions['neuralmind_version']}: the index and the hooks would differ",
            file=sys.stderr,
        )
        return 2
    pin = hermes_plugin_pin() if args.agent == "hermes" else None
    if pin:
        print(
            f"error: the Hermes plugin is pinned to {pin}, so every run would "
            "get that project's context, not its workspace's: reinstall it with "
            "`neuralmind install-hermes-plugin --unpin`",
            file=sys.stderr,
        )
        return 2
    triples = plan(tasks, arms, args.seeds, args.order_seed)

    args.out.mkdir(parents=True, exist_ok=True)
    runs_file = args.out / "runs.jsonl"
    done = set()
    if runs_file.is_file():
        for line in runs_file.read_text().splitlines():
            r = json.loads(line)
            done.add((r["task"], r["arm"], r["seed"]))
            mixed = {k: (r.get(k), v) for k, v in args.versions.items() if r.get(k) != v}
            if mixed:
                print(
                    f"error: {runs_file} was recorded with other versions: {mixed}", file=sys.stderr
                )
                return 2
    todo = [t for t in triples if t not in done]
    print(f"{len(triples)} run(s) planned, {len(todo)} to do")

    if args.dry_run:
        if todo:
            tid, arm, _ = todo[0]
            print(f"versions: {args.versions}")
            if args.agent == "hermes":
                cmd = hermes_command(args.agent_bin, Path("<ws>.prompt.txt"), args.max_turns)
                print(" ".join(cmd))
            else:
                cmd = claude_command(
                    args.agent_bin,
                    PROMPT.format(symptom=by_id[tid]["prompt"].strip()),
                    arm,
                    args.model,
                    Path("<ws>/.bench-mcp.json"),
                    args.budget,
                )
                print(" ".join(cmd[:2] + ["<prompt>"] + cmd[3:]))
            for a in arms:
                _arm_env(a, args.tool_venv, args.test_python)  # raises if PATH leaks
            print("PATH isolation: ok for every arm")
        return 0

    args.work_dir.mkdir(parents=True, exist_ok=True)
    for i, (tid, arm, seed) in enumerate(todo, 1):
        try:
            record = run_one(by_id[tid], arm, seed, args)
        except RunAbortedError as exc:
            print(f"aborted, nothing recorded: {exc}", file=sys.stderr)
            return 3
        with runs_file.open("a") as fh:
            fh.write(json.dumps(record) + "\n")
        usage = (
            f"tokens={record['total_tokens']}"
            if args.agent == "hermes"
            else f"cost=${record['cost_usd']}"
        )
        print(
            f"[{i}/{len(todo)}] {tid} {arm} s{seed}: solved={record['solved']} "
            f"{usage} turns={record['num_turns']}",
            flush=True,
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
