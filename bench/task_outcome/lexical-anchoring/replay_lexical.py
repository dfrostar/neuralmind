# SPDX-License-Identifier: MIT
"""Lexical anchoring, replayed offline on cached indexes: the script behind README.md.

    python replay_lexical.py prepare <set>                  export each task's base commit
    python replay_lexical.py capture <set>                  one search per task (n=128), cached
    python replay_lexical.py variants <set> [weight ...]    in-process recall(), flag off and on
    python replay_lexical.py hook <set> <shim-dir> <label>  the real `neuralmind _hook prompt-submit`
    python replay_lexical.py summary                        the README's tables from the results here

``<set>`` is ``heldout`` (the 12 held-out hermes-agent tasks of
``../hermes-agent-test-ranking/heldout/tasks.json``), ``dev`` (the hermes-agent
screen's 5 tasks, the ranking changes' tuning set) or ``pilot`` (the 20 tasks
of ``evals/task_outcome/tasks.json`` on this repository). Each task's index was
built once with v4.22.1 for the test-ranking study and is reused from the
caches under ``$NM_BENCH`` (default ``~/nm-bench``), so the flag is the only
difference between a flag-off and a flag-on row. Every hook call and every
in-process recall runs on a fresh APFS clone of the task's index, so no replay
sees another's writes.

A ``<shim-dir>`` holds a ``neuralmind`` executable that runs the NeuralMind
under test, setting ``NEURALMIND_RECALL_LEXICAL`` itself: the hook's
environment is cleaned of every ``NEURALMIND_*`` variable, as the task-outcome
harness cleans it. ``capture``, ``variants`` and ``hook`` embed and load
hermes-agent-scale graphs: run one at a time. Nothing here runs hermes-agent
code, and nothing writes to either repository.

It is a record of how the numbers in this folder were produced. It imports
``evals.task_outcome`` from this checkout.
"""

from __future__ import annotations

import contextlib
import io
import json
import os
import re
import shutil
import statistics
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
sys.path.insert(0, str(REPO))

from evals.task_outcome import harness, profiles, replay  # noqa: E402
from evals.task_outcome.run import render_prompt  # noqa: E402
from neuralmind import prompt_recall  # noqa: E402

BENCH = Path(os.environ.get("NM_BENCH") or Path.home() / "nm-bench")
OUT = BENCH / "lexical"
RANKING = HERE.parent / "hermes-agent-test-ranking"
HERMES_REPO = BENCH / "hermes-agent"
SEARCH_N = 128
# The pre-registered grid (docs/specs/TASK-OUTCOME-BENCHMARK-SPEC.md, 2026-11-01).
WEIGHTS = (0.25, 0.5, 1.0)

SETS = {
    "heldout": {
        "tasks": RANKING / "heldout" / "tasks.json",
        "index": BENCH / "heldout" / "index",
        "ws": BENCH / "heldout" / "ws",
        "hits": BENCH / "heldout" / "hits",
        "repo": HERMES_REPO,
        "profile": "hermes-agent",
    },
    "dev": {
        "tasks": REPO / "evals" / "task_outcome" / "studies" / "hermes-agent-screen" / "tasks.json",
        "index": BENCH / "index-cache",
        "ws": OUT / "ws" / "dev",
        "hits": BENCH / "heldout" / "hits",
        "repo": HERMES_REPO,
        "profile": "hermes-agent",
    },
    "pilot": {
        "tasks": REPO / "evals" / "task_outcome" / "tasks.json",
        "index": BENCH / "pilot-merged",
        "ws": OUT / "ws" / "pilot",
        "hits": OUT / "hits",
        "repo": None,  # this repository
        "profile": profiles.DEFAULT,
    },
}


def tasks(which: str) -> list[dict]:
    return json.loads(Path(SETS[which]["tasks"]).read_text())


def index_of(which: str, tid: str) -> Path:
    return SETS[which]["index"] / tid / ".neuralmind"


def ws_of(which: str, tid: str) -> Path:
    return SETS[which]["ws"] / tid


def prompt_of(which: str, task: dict) -> str:
    return render_prompt(task["prompt"], profiles.get(SETS[which]["profile"]))


def use_repo(which: str) -> None:
    repo = SETS[which]["repo"]
    if repo is not None:
        harness.use_repo(repo)


def prepare(which: str) -> None:
    use_repo(which)
    for task in tasks(which):
        ws = ws_of(which, task["id"])
        if not ws.is_dir():
            harness.snapshot(task["base_commit"], ws)
        restore(which, task["id"])
        print(task["id"], "ready", flush=True)


def restore(which: str, tid: str) -> None:
    ws = ws_of(which, tid)
    shutil.rmtree(ws / ".neuralmind", ignore_errors=True)
    # APFS clone: instant, and nothing a run writes reaches the cached index.
    subprocess.run(["cp", "-cR", str(index_of(which, tid)), str(ws / ".neuralmind")], check=True)


def _mind(ws: Path):
    from neuralmind.core import NeuralMind

    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        mind = NeuralMind(str(ws))
        # As the hook loads it: no structural index.
        assert mind._load_existing_index(structural=False), ws
    return mind


def capture(which: str) -> None:
    SETS[which]["hits"].mkdir(parents=True, exist_ok=True)
    for task in tasks(which):
        dest = SETS[which]["hits"] / f"{task['id']}.json"
        if dest.is_file():
            continue
        restore(which, task["id"])
        hits = _mind(ws_of(which, task["id"])).embedder.search(prompt_of(which, task), n=SEARCH_N)
        keep = [
            {"id": h["id"], "score": h["score"], "metadata": h.get("metadata") or {}} for h in hits
        ]
        dest.write_text(json.dumps(keep))
        print(task["id"], len(keep), "hits", flush=True)


def _record(which: str, task: dict, block: str, changed: dict) -> dict:
    record = {"task": task["id"], "gold": task["gold_files"]}
    record.update(replay.score(block, task, changed))
    record["tests_listed"] = sum(prompt_recall.is_test_path(p) for p in record["listed"])
    return record


def _summary(records: list[dict], **extra) -> dict:
    summary = {**extra, **replay.summarize(records)}
    summary["tests_listed"] = sum(r["tests_listed"] for r in records)
    summary["files_listed"] = sum(len(r["listed"]) for r in records)
    seconds = [r["seconds"] for r in records if "seconds" in r]
    if seconds:
        summary["median_seconds"] = round(statistics.median(seconds), 2)
    return summary


def _lexical_replica(which: str, tid: str) -> dict:
    """What the hook's lexical pass saw, recomputed on the same workspace: one process per task.

    It loads the task's graph, as the hook does, and uses the hook's own
    matcher (``prompt_recall._lexical_matches``), so the eligibility filter,
    the frequency cut and the scores are the ranking's.
    """
    proc = subprocess.run(
        [sys.executable, "-P", __file__, "_replica", which, tid],
        capture_output=True,
        text=True,
        check=True,
    )
    return json.loads(proc.stdout.splitlines()[-1])


def _replica(which: str, tid: str) -> None:
    use_repo(which)
    task = next(t for t in tasks(which) if t["id"] == tid)
    ws = ws_of(which, tid)
    prompt = prompt_of(which, task)
    nodes = prompt_recall._node_index(_mind(ws))
    identifiers = prompt_recall.extract_identifiers(prompt)
    matches = prompt_recall._lexical_matches(
        str(ws),
        identifiers,
        prompt_recall._IndexedFiles(nodes),
        not prompt_recall._names_a_test(prompt),
    )
    cap = prompt_recall.LEXICAL_MAX_FILES
    print(
        json.dumps(
            {
                "identifiers": identifiers,
                # The files of each identifier that counted; an identifier past
                # the cap (in hundreds of files, say) is recorded by its count.
                "matched": {i: sorted(f) for i, f in matches.items() if len(f) <= cap},
                "dropped_too_common": {i: len(f) for i, f in matches.items() if len(f) > cap},
                "lexical": {
                    path: round(score, 4)
                    for path, score in prompt_recall.lexical_file_scores(matches).items()
                },
            }
        )
    )


def hook(which: str, shim: str, label: str) -> None:
    use_repo(which)
    env = {k: v for k, v in os.environ.items() if not k.startswith("NEURALMIND_")}
    env["PATH"] = f"{shim}{os.pathsep}{env['PATH']}"
    version = subprocess.run(
        ["neuralmind", "--version"], env=env, capture_output=True, text=True, check=True
    ).stdout.strip()
    # What the shim exports for the flag, read from its text (sourcing it would run it).
    match = re.search(
        rf"{prompt_recall.LEXICAL_ENV}=(\S+)", (Path(shim) / "neuralmind").read_text()
    )
    flag = match.group(1) if match else "unset"
    out = OUT / "out" / which / label
    (out / "blocks").mkdir(parents=True, exist_ok=True)
    records = []
    for task in tasks(which):
        restore(which, task["id"])
        prompt = prompt_of(which, task)
        t0 = time.monotonic()
        block = replay.hook_block(ws_of(which, task["id"]), prompt, env)
        seconds = time.monotonic() - t0
        record = _record(which, task, block, replay.fix_lines(task))
        record["seconds"] = round(seconds, 2)
        record["lexical_replica"] = _lexical_replica(which, task["id"])
        records.append(record)
        (out / "blocks" / f"{task['id']}.md").write_text(block)
        print(
            task["id"],
            "named" if record["named"] else "-",
            "first" if record["first"] else "-",
            f"{seconds:.1f}s",
            record["listed"][:3],
            flush=True,
        )
    summary = _summary(
        records,
        neuralmind_version=version,
        lexical_flag=flag,
        lexical_weight=prompt_recall.LEXICAL_WEIGHT,
        shim=str(Path(shim).resolve()),
    )
    results = {"summary": summary, "tasks": records}
    (out / "replay-results.json").write_text(json.dumps(results, indent=2) + "\n")
    dest = HERE / which / label
    dest.mkdir(parents=True, exist_ok=True)
    (dest / "replay-results.json").write_text(json.dumps(results, indent=2) + "\n")
    print(json.dumps(summary, indent=2))


def variants(which: str, weights: list[float]) -> None:
    """Flag off, and on at each weight, on the cached hits: one task per process.

    A hermes-agent graph is 1.75 GB in memory; a process per task gives it back.
    """
    rows: dict[str, list[dict]] = {}
    for task in tasks(which):
        proc = subprocess.run(
            [sys.executable, "-P", __file__, "_variant", which, task["id"], *map(str, weights)],
            capture_output=True,
            text=True,
            check=True,
        )
        for name, record in json.loads(proc.stdout.splitlines()[-1]).items():
            rows.setdefault(name, []).append(record)
        print(task["id"], "done", flush=True)
    for name, records in rows.items():
        s = _summary(records)
        print(
            f"{name:12} named {s['named']}/{s['tasks']} first {s['first']} "
            f"excerpt {s['excerpt_on_gold']}/{s['excerpt_shown']} "
            f"tests {s['tests_listed']}/{s['files_listed']}"
        )
    (HERE / f"variants-{which}.json").write_text(json.dumps(rows, indent=1) + "\n")


def _variant(which: str, tid: str, weights: list[float]) -> None:
    use_repo(which)
    task = next(t for t in tasks(which) if t["id"] == tid)
    hits = json.loads((SETS[which]["hits"] / f"{tid}.json").read_text())
    restore(which, tid)
    mind = _mind(ws_of(which, tid))
    # The cached search, so every variant ranks the same hits.
    mind.embedder.search = lambda query, n=16, _h=hits, **kw: [dict(h) for h in _h[:n]]
    prompt = prompt_of(which, task)
    changed = replay.fix_lines(task)
    out: dict[str, dict] = {}
    saved = prompt_recall.LEXICAL_WEIGHT
    for name, weight in [("off", None), *((f"on_{w:g}", w) for w in weights)]:
        if weight is None:
            os.environ.pop(prompt_recall.LEXICAL_ENV, None)
        else:
            os.environ[prompt_recall.LEXICAL_ENV] = "1"
            prompt_recall.LEXICAL_WEIGHT = weight
        try:
            result = prompt_recall.recall(mind, prompt)
        finally:
            prompt_recall.LEXICAL_WEIGHT = saved
        record = _record(which, task, prompt_recall.format_block(result), changed)
        record["identifiers"] = result.identifiers
        record["lexical"] = {p: round(s, 4) for p, s in result.lexical.items()}
        out[name] = record
    os.environ.pop(prompt_recall.LEXICAL_ENV, None)
    print(json.dumps(out))


def _load(which: str, label: str) -> dict | None:
    path = HERE / which / label / "replay-results.json"
    return json.loads(path.read_text()) if path.is_file() else None


def summary() -> None:
    """The README's tables, from the committed results."""
    for which in ("heldout", "dev", "pilot"):
        off, on = _load(which, "flag-off"), _load(which, "flag-on")
        if off is None or on is None:
            continue
        s_off, s_on = off["summary"], on["summary"]
        print(f"\n### {which} ({s_off['tasks']} tasks)\n")
        print("| | flag off | flag on |\n|---|---|---|")
        print(f"| A file the fix changed is listed | {s_off['named']} | {s_on['named']} |")
        print(f"| …and listed first | {s_off['first']} | {s_on['first']} |")
        print(
            f"| Code quoted / from a changed file | {s_off['excerpt_shown']} / "
            f"{s_off['excerpt_on_gold']} | {s_on['excerpt_shown']} / {s_on['excerpt_on_gold']} |"
        )
        print(
            f"| Test files among the files listed | {s_off['tests_listed']} of "
            f"{s_off['files_listed']} | {s_on['tests_listed']} of {s_on['files_listed']} |"
        )
        print(
            f"| Median block size (characters) | {s_off['median_chars']} | {s_on['median_chars']} |"
        )
        print(
            f"| Median hook time (seconds) | {s_off.get('median_seconds')} | "
            f"{s_on.get('median_seconds')} |"
        )
        by_off = {r["task"]: r for r in off["tasks"]}
        print("\n| Task | Gold | Off: first file | named/first | On: first file | named/first |")
        print("|---|---|---|---|---|---|")
        for r in on["tasks"]:
            o = by_off[r["task"]]
            print(
                f"| `{r['task']}` | {', '.join(r['gold'])} | {_first(o)} | {_mark(o)} | "
                f"{_first(r)} | {_mark(r)} |"
            )


def _mark(record: dict) -> str:
    return ("named" if record["named"] else "-") + ("/first" if record["first"] else "")


def _first(record: dict) -> str:
    return record["listed"][0] if record["listed"] else "(nothing)"


if __name__ == "__main__":
    cmd, *rest = sys.argv[1:] or ["help"]
    if cmd == "prepare":
        prepare(rest[0])
    elif cmd == "capture":
        use_repo(rest[0])
        capture(rest[0])
    elif cmd == "variants":
        variants(rest[0], [float(w) for w in rest[1:]] or list(WEIGHTS))
    elif cmd == "_variant":
        _variant(rest[0], rest[1], [float(w) for w in rest[2:]])
    elif cmd == "_replica":
        _replica(rest[0], rest[1])
    elif cmd == "hook":
        hook(rest[0], rest[1], rest[2])
    elif cmd == "summary":
        summary()
    else:
        sys.exit(__doc__)
