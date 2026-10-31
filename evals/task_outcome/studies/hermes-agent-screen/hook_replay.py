"""What the prompt hook showed the agent on the screen's 5 tasks, scored offline.

Claude Code's stream doesn't record a UserPromptSubmit hook's output, so the
transcripts can't show it. This rebuilds each task's workspace from the parent
commit, restores the index the runs used (--index-cache), pipes the task's
prompt into `neuralmind _hook prompt-submit` and scores the block with
replay.score(). No agent, no API cost. Run after the screen, with its paths:

    PATH=~/nm-bench/tool-venv/bin:$PATH ~/nm-bench/test-venv/bin/python hook_replay.py
"""

from __future__ import annotations

import json
import os
import shutil
import sys
from pathlib import Path

BENCH = Path.home() / "nm-bench"
sys.path.insert(0, str(BENCH / "harness"))

from evals.task_outcome import harness, profiles, replay  # noqa: E402
from evals.task_outcome.run import render_prompt  # noqa: E402

OUT = BENCH / "replay"


def main() -> int:
    harness.use_repo(BENCH / "hermes-agent")
    profile = profiles.get("hermes-agent")
    env = {k: v for k, v in os.environ.items() if not k.startswith("NEURALMIND_")}
    env["PATH"] = f"{BENCH / 'tool-venv' / 'bin'}{os.pathsep}{env['PATH']}"
    records = []
    for task in json.loads((BENCH / "study" / "tasks.json").read_text()):
        ws = OUT / "ws" / task["id"]
        shutil.rmtree(ws, ignore_errors=True)
        harness.snapshot(task["base_commit"], ws)
        shutil.copytree(BENCH / "index-cache" / task["id"] / ".neuralmind", ws / ".neuralmind")
        block = replay.hook_block(ws, render_prompt(task["prompt"], profile), env)
        record = {"task": task["id"], "gold": task["gold_files"]}
        record.update(replay.score(block, task, replay.fix_lines(task)))
        records.append(record)
        (OUT / "blocks").mkdir(parents=True, exist_ok=True)
        (OUT / "blocks" / f"{task['id']}.md").write_text(block)
        shutil.rmtree(ws)
        print(
            task["id"],
            "named" if record["named"] else "not named",
            record["listed"][:5],
            flush=True,
        )
    summary = replay.summarize(records)
    (OUT / "replay-results.json").write_text(
        json.dumps({"summary": summary, "tasks": records}, indent=2) + "\n"
    )
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
