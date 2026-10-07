"""Calibration for the prompt-time recall gate.

The UserPromptSubmit hook used to inject up to 8 associated nodes on every
prompt once the synapse graph had any edges, including "yes", "continue" and
questions about something else entirely: a prompt always has nearest
neighbours in the index, however poor the match. The hook now abstains when
the best match scores below ``DEFAULT_RECALL_MIN_SIMILARITY`` in
``neuralmind/hooks.py``. This module is where that number comes from.

It runs two fixed prompt sets through ``neuralmind.prompt_recall.recall``, the
call the hook makes: prompts about the NeuralMind code itself, and off-topic
prompts (short agent-session replies, general questions, other domains). For
each it reports the best-match similarity and how many files the block would
name, then sweeps candidate thresholds: on-topic prompts kept against
off-topic prompts let through.

The on-topic set is about this repository, so run it against a built
NeuralMind checkout. It lives in ``tests/``, which the PyPI package doesn't
include, so it needs a source checkout. It measures the current code only:
``would_inject`` is recall without the gate, the sweep is the gate. ``--prompts`` takes a JSON file with ``on_topic`` and
``off_topic`` lists to calibrate on another project. Read-only: learning is
switched off for the run.

Run it::

    neuralmind build .
    python -m tests.benchmark.recall_gate .           # human-readable
    python -m tests.benchmark.recall_gate . --json    # machine-readable
"""

from __future__ import annotations

import argparse
import contextlib
import io
import json
import os
import sys
from pathlib import Path

ON_TOPIC = [
    "how does synapse decay work",
    "where is the PreCompact hook handled",
    "add a threshold to the spreading activation recall in the prompt-submit hook",
    "why does the session recap skip resumed sessions",
    "fix the claims guard test for site numbers",
    "the hermes plugin isn't injecting context, debug it",
    "how are team memory bundles imported on session start",
    "what does fit_to_budget trim first",
    "make the MCP query tool report a stale index",
    "the decision store marks decisions stale on commit, where is that",
    "rename synaptic_neighbors to associative_recall everywhere",
    "how is the bash output cache redacted",
    "explain the L0 L1 L2 L3 context layers",
    "why did the public benchmark recall drop on rich",
    "add a new env var to disable the read dedup",
]

OFF_TOPIC = [
    "yes",
    "go ahead",
    "looks good, commit it",
    "continue",
    "thanks!",
    "what's the capital of France",
    "write a haiku about autumn",
    "how do I center a div in CSS",
    "explain kubernetes pod scheduling",
    "what time zone is Texas in",
    "draft an email to my landlord about the leak",
    "convert 5 miles to kilometers",
    "what is a monad in haskell",
    "recommend a good sci-fi book",
    "how do I make sourdough starter",
]

THRESHOLDS = (0.25, 0.30, 0.33, 0.35, 0.37, 0.40)


def measure(project: str, on_topic: list[str], off_topic: list[str]) -> dict:
    os.environ["NEURALMIND_NO_LEARN"] = "1"
    from neuralmind.core import NeuralMind
    from neuralmind.prompt_recall import recall

    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        mind = NeuralMind(project)
        if not mind._load_existing_index():
            raise SystemExit(f"no index in {project}: run `neuralmind build {project}` first")
    rows = []
    for label, prompts in (("on_topic", on_topic), ("off_topic", off_topic)):
        for prompt in prompts:
            with (
                contextlib.redirect_stdout(io.StringIO()),
                contextlib.redirect_stderr(io.StringIO()),
            ):
                result = recall(mind, prompt)
            rows.append(
                {
                    "set": label,
                    "prompt": prompt,
                    "similarity": round(result.similarity, 4),
                    "would_inject": result.count,
                }
            )
    sweep = []
    for threshold in THRESHOLDS:
        sweep.append(
            {
                "threshold": threshold,
                "on_topic_kept": sum(
                    1 for r in rows if r["set"] == "on_topic" and r["similarity"] >= threshold
                ),
                "off_topic_passed": sum(
                    1 for r in rows if r["set"] == "off_topic" and r["similarity"] >= threshold
                ),
            }
        )
    return {
        "project": str(Path(project).resolve().name),
        "n_on_topic": len(on_topic),
        "n_off_topic": len(off_topic),
        "rows": rows,
        "sweep": sweep,
    }


def _print(report: dict) -> None:
    for label in ("on_topic", "off_topic"):
        rows = [r for r in report["rows"] if r["set"] == label]
        sims = [r["similarity"] for r in rows]
        print(f"{label}: similarity {min(sims):.3f}-{max(sims):.3f}")
        for r in sorted(rows, key=lambda r: r["similarity"]):
            print(f"  {r['similarity']:.3f}  inject {r['would_inject']}  {r['prompt']}")
    print()
    print(f"{'threshold':>9}  {'on-topic kept':>14}  {'off-topic passed':>17}")
    for s in report["sweep"]:
        print(
            f"{s['threshold']:>9.2f}  {s['on_topic_kept']:>8}/{report['n_on_topic']:<5}"
            f"  {s['off_topic_passed']:>10}/{report['n_off_topic']}"
        )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("project", nargs="?", default=".", help="a built NeuralMind project")
    parser.add_argument("--prompts", help="JSON file with on_topic and off_topic lists")
    parser.add_argument("--json", action="store_true", help="machine-readable output")
    args = parser.parse_args(argv)
    on_topic, off_topic = ON_TOPIC, OFF_TOPIC
    if args.prompts:
        data = json.loads(Path(args.prompts).read_text(encoding="utf-8"))
        on_topic, off_topic = data["on_topic"], data["off_topic"]
    report = measure(args.project, on_topic, off_topic)
    if args.json:
        json.dump(report, sys.stdout, indent=2)
        print()
    else:
        _print(report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
