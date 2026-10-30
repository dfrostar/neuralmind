"""Draw the pilot's tasks from the harvested candidates, by the pre-registered rule.

    python -m evals.task_outcome.select_tasks --candidates <scratch>/candidates.json \\
        --python <test-venv>/bin/python --work-dir <scratch> \\
        [--order-only] [--n 20]

Candidates are shuffled with a fixed seed and walked in that order. A candidate
listed in ``exclusions.json`` is skipped, and its reason recorded. Every other
candidate is harvested a second time; it is accepted only if it gives the same
FAIL_TO_PASS and PASS_TO_PASS tests as the first time, which rules out flaky
oracles. The first ``--n`` accepted candidates become ``tasks.json``, each
with its prompt from ``prompts.json``.

``--order-only`` prints the seeded order and stops, so prompts can be written
for the candidates that will be reached before any are checked or run.
"""

from __future__ import annotations

import argparse
import json
import random
import sys
from pathlib import Path

from evals.task_outcome import harness, harvest, profiles

HERE = Path(__file__).parent
SEED = 20261014


def seeded_order(candidates: list[dict], seed: int = SEED) -> list[dict]:
    ordered = sorted(candidates, key=lambda t: t["fix_commit"])
    random.Random(seed).shuffle(ordered)
    return ordered


def prompt_leaks(task: dict, prompt: str) -> list[str]:
    """Gold file names (with or without ``.py``) that appear in the prompt."""
    text = prompt.lower()
    leaks = []
    for path in task["gold_files"]:
        name = Path(path).name.lower()
        stem = Path(path).stem.lower()
        if name in text or (stem != "__init__" and stem in text.replace(" ", "_")):
            leaks.append(name)
    return leaks


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--candidates", type=Path, required=True)
    ap.add_argument("--python")
    ap.add_argument("--work-dir", type=Path)
    ap.add_argument("--n", type=int, default=20)
    ap.add_argument("--order-only", action="store_true")
    ap.add_argument(
        "--study-dir",
        type=Path,
        default=HERE,
        help="holds exclusions.json and prompts.json (default: the pilot's, here)",
    )
    ap.add_argument("--out", type=Path, help="default: <study-dir>/tasks.json")
    ap.add_argument("--seed", type=int, default=SEED, help="the study's pre-registered seed")
    ap.add_argument("--repo", type=Path, help="clone the candidates came from")
    ap.add_argument("--profile", default=profiles.DEFAULT, choices=sorted(profiles.PROFILES))
    args = ap.parse_args(argv)
    if args.repo:
        harness.use_repo(args.repo)
    profile = profiles.get(args.profile)
    out = args.out or args.study_dir / "tasks.json"

    ordered = seeded_order(json.loads(args.candidates.read_text()), args.seed)
    exclusions = json.loads((args.study_dir / "exclusions.json").read_text())
    if args.order_only:
        for i, t in enumerate(ordered, 1):
            mark = f"  EXCLUDED: {exclusions[t['id']]}" if t["id"] in exclusions else ""
            print(f"{i:2d}. {t['id']}  {t['subject'][:80]}{mark}")
        return 0

    prompts = json.loads((args.study_dir / "prompts.json").read_text())
    accepted: list[dict] = []
    for t in ordered:
        if len(accepted) == args.n:
            break
        if t["id"] in exclusions:
            print(f"{t['id']}: excluded — {exclusions[t['id']]}")
            continue
        prompt = prompts.get(t["id"], "").strip()
        if not prompt:
            print(f"error: no prompt for {t['id']}, which the draw reaches", file=sys.stderr)
            return 2
        leaks = prompt_leaks(t, prompt)
        if leaks:
            print(f"error: the prompt for {t['id']} names {', '.join(leaks)}", file=sys.stderr)
            return 2
        again = harvest.harvest_one(t["fix_commit"], args.python, args.work_dir, profile)
        stable = bool(again) and (
            again["fail_to_pass"] == t["fail_to_pass"]
            and again["pass_to_pass"] == t["pass_to_pass"]
        )
        if not stable:
            print(f"{t['id']}: excluded — oracle changed on a second harvest (flaky)")
            continue
        accepted.append({**t, "prompt": prompt})
        print(f"{t['id']}: accepted ({len(accepted)}/{args.n})")

    if len(accepted) < args.n:
        print(f"error: only {len(accepted)} task(s) qualified", file=sys.stderr)
        return 1
    out.write_text(json.dumps(accepted, indent=2) + "\n")
    print(f"wrote {len(accepted)} task(s) to {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
