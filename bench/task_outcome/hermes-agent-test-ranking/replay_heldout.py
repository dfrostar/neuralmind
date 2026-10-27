# SPDX-License-Identifier: MIT
"""Score the prompt hook's block on hermes-agent tasks, offline: the script behind README.md.

    python replay_heldout.py build <set> <shim-dir> <task-id>...  one fresh index per task
    python replay_heldout.py prepare <set>             export each task's parent commit
    python replay_heldout.py hook <set> <shim-dir> <label>   the real `neuralmind _hook prompt-submit`
    python replay_heldout.py capture <set>             one search per task (n=128), cached
    python replay_heldout.py variants <set>            in-process recall() per ranking variant

It is a record of how the numbers in this folder were produced, not a tool on
``main``: it imports the task-outcome harness from the branch that runs it on
another repository (``evals/task_outcome`` at 79d46eb9, PRs #719 and #720,
checked out at ``~/nm-bench/harness``), which ``main``'s harness predates.

``<set>`` is ``dev`` (the hermes-agent screen's 5 tasks, ranking tuned on them)
or ``heldout`` (``heldout/tasks.json``). A ``<shim-dir>`` holds a ``neuralmind``
executable that runs the NeuralMind under test. Every hook call restores an
APFS clone of the task's index, so no replay sees another's writes. ``build``,
``capture`` and ``hook`` embed: run one at a time, never beside a build. None
of it runs hermes-agent code.
"""

from __future__ import annotations

import contextlib
import io
import json
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

from neuralmind import prompt_recall  # before the harness checkout shadows it

BENCH = Path.home() / "nm-bench"
sys.path.insert(0, str(BENCH / "harness"))
sys.modules.pop("evals", None)
from evals.task_outcome import harness, profiles, replay  # noqa: E402
from evals.task_outcome.run import render_prompt  # noqa: E402

HERE = Path(__file__).resolve().parent
OUT = BENCH / "heldout"
PROFILE = profiles.get("hermes-agent")

# The rule v4.22.1 used: any mention of tests.
OLD_TEST_PROMPT = re.compile(r"\b(tests?|testing|specs?|pytest|unittest)\b", re.IGNORECASE)
# name -> (v4.22.1's about-tests rule, TESTED_CODE_CREDIT)
VARIANTS = {"main": (True, 0.0), "A_tests_last": (False, 0.0), "A+C1.0": (False, 1.0)}


def tasks(which: str) -> list[dict]:
    if which == "dev":
        return json.loads((BENCH / "study" / "tasks.json").read_text())
    return json.loads((HERE / "heldout" / "tasks.json").read_text())


def index_of(which: str, tid: str) -> Path:
    if which == "dev":
        return BENCH / "index-cache" / tid / ".neuralmind"
    return OUT / "index" / tid / ".neuralmind"


def ws_of(tid: str) -> Path:
    return OUT / "ws" / tid


def prompt_of(task: dict) -> str:
    return render_prompt(task["prompt"], PROFILE)


def shim_env(shim: str) -> dict[str, str]:
    env = {k: v for k, v in os.environ.items() if not k.startswith("NEURALMIND_")}
    env["PATH"] = f"{shim}{os.pathsep}{env['PATH']}"
    return env


def build(which: str, shim: str, ids: list[str]) -> None:
    env = shim_env(shim)
    by_id = {task["id"]: task for task in tasks(which)}
    for tid in ids:
        idx = index_of(which, tid)
        if idx.is_dir():
            print(f"{tid}: already built", flush=True)
            continue
        ws = OUT / "build-ws" / tid
        shutil.rmtree(ws, ignore_errors=True)
        harness.snapshot(by_id[tid]["base_commit"], ws)
        t0 = time.monotonic()
        subprocess.run(["neuralmind", "build", str(ws)], cwd=ws, env=env, check=True)
        idx.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(ws / ".neuralmind"), str(idx))
        shutil.rmtree(ws)
        print(f"{tid}: built in {time.monotonic() - t0:.0f}s", flush=True)


def prepare(which: str) -> None:
    for task in tasks(which):
        if not ws_of(task["id"]).is_dir():
            harness.snapshot(task["base_commit"], ws_of(task["id"]))
        restore(which, task["id"])
        print(task["id"], "ready", flush=True)


def restore(which: str, tid: str) -> None:
    ws = ws_of(tid)
    shutil.rmtree(ws / ".neuralmind", ignore_errors=True)
    # APFS clone: instant, and nothing a run writes reaches the cached index.
    subprocess.run(["cp", "-cR", str(index_of(which, tid)), str(ws / ".neuralmind")], check=True)


def hook(which: str, shim: str, label: str) -> None:
    env = shim_env(shim)
    version = subprocess.run(
        ["neuralmind", "--version"], env=env, capture_output=True, text=True, check=True
    ).stdout.strip()
    out = OUT / "hook" / which / label
    (out / "blocks").mkdir(parents=True, exist_ok=True)
    records = []
    for task in tasks(which):
        restore(which, task["id"])
        block = replay.hook_block(ws_of(task["id"]), prompt_of(task), env)
        record = {"task": task["id"], "gold": task["gold_files"]}
        record.update(replay.score(block, task, replay.fix_lines(task)))
        record["tests_listed"] = sum(prompt_recall.is_test_path(p) for p in record["listed"])
        records.append(record)
        (out / "blocks" / f"{task['id']}.md").write_text(block)
        print(task["id"], "named" if record["named"] else "-", record["listed"][:4], flush=True)
    summary = {"neuralmind_version": version, **replay.summarize(records)}
    summary["tests_listed"] = sum(r["tests_listed"] for r in records)
    summary["files_listed"] = sum(len(r["listed"]) for r in records)
    (out / "replay-results.json").write_text(
        json.dumps({"summary": summary, "tasks": records}, indent=2) + "\n"
    )
    print(json.dumps(summary, indent=2))


def _mind(ws: Path):
    from neuralmind.core import NeuralMind

    with contextlib.redirect_stdout(io.StringIO()):
        mind = NeuralMind(str(ws))
        assert mind._load_existing_index(), ws
    return mind


def capture(which: str) -> None:
    (OUT / "hits").mkdir(parents=True, exist_ok=True)
    for task in tasks(which):
        dest = OUT / "hits" / f"{task['id']}.json"
        if dest.is_file():
            continue
        hits = _mind(ws_of(task["id"])).embedder.search(prompt_of(task), n=128)
        keep = [
            {"id": h["id"], "score": h["score"], "metadata": h.get("metadata") or {}} for h in hits
        ]
        dest.write_text(json.dumps(keep))
        print(task["id"], len(keep), "hits", flush=True)


@contextlib.contextmanager
def _variant(name: str):
    old_rule, credit = VARIANTS[name]
    saved = (prompt_recall.about_tests, prompt_recall.TESTED_CODE_CREDIT)
    if old_rule:
        prompt_recall.about_tests = lambda p: bool(OLD_TEST_PROMPT.search(p))
    prompt_recall.TESTED_CODE_CREDIT = credit
    try:
        yield
    finally:
        prompt_recall.about_tests, prompt_recall.TESTED_CODE_CREDIT = saved


def variants(which: str) -> None:
    rows: dict[str, list[dict]] = {}
    for task in tasks(which):
        hits = json.loads((OUT / "hits" / f"{task['id']}.json").read_text())
        mind = _mind(ws_of(task["id"]))
        # The cached search, so every variant ranks the same hits.
        mind.embedder.search = lambda query, n=16, _h=hits, **kw: [dict(h) for h in _h[:n]]
        changed = replay.fix_lines(task)
        for name in VARIANTS:
            with _variant(name):
                result = prompt_recall.recall(mind, prompt_of(task))
                block = prompt_recall.format_block(result)
            record = {"task": task["id"], "gold": task["gold_files"]}
            record.update(replay.score(block, task, changed))
            rows.setdefault(name, []).append(record)
    for name, records in rows.items():
        s = replay.summarize(records)
        tests = sum(prompt_recall.is_test_path(p) for r in records for p in r["listed"])
        listed = sum(len(r["listed"]) for r in records)
        print(
            f"{name:14} named {s['named']}/{s['tasks']} first {s['first']} "
            f"excerpt {s['excerpt_on_gold']}/{s['excerpt_shown']} tests {tests}/{listed}"
        )
    (HERE / f"variants-{which}.json").write_text(json.dumps(rows, indent=1) + "\n")


if __name__ == "__main__":
    harness.use_repo(BENCH / "hermes-agent")
    cmd, which, *rest = sys.argv[1:]
    if cmd == "build":
        build(which, rest[0], rest[1:])
    elif cmd == "prepare":
        prepare(which)
    elif cmd == "hook":
        hook(which, rest[0], rest[1])
    elif cmd == "capture":
        capture(which)
    elif cmd == "variants":
        variants(which)
    else:
        sys.exit(__doc__)
