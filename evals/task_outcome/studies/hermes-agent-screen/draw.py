"""Draw hermes-agent candidates in a seeded order and harvest them until enough qualify.

The pilot harvested every candidate and then shuffled; here there are
thousands, so the metadata gates (subject, date, source files, a changed
tests/**/test_*.py) are applied from git log first, the survivors are sorted
by hash and shuffled with the study's seed, and harvest_one() walks that order
until --want candidates have a FAIL_TO_PASS test. Each commit's outcome
(qualified, or why not) is appended to walk.jsonl, so the walk resumes.

    python draw.py --want 12
"""

from __future__ import annotations

import argparse
import json
import random
import re
import sys
from pathlib import Path

HARNESS = Path.home() / "nm-bench" / "harness"
sys.path.insert(0, str(HARNESS))

from evals.task_outcome import harness, harvest, profiles  # noqa: E402

REPO = Path.home() / "nm-bench" / "hermes-agent"
STUDY = Path.home() / "nm-bench" / "study"
PYTHON = str(Path.home() / "nm-bench" / "test-venv" / "bin" / "python")
SEED = 20261025
TEST_RE = re.compile(r"^tests/(.+/)?test_[^/]*\.py$")


def eligible_by_metadata(profile: profiles.Profile) -> list[str]:
    log = harness.git(
        "log",
        "origin/main",
        "--no-merges",
        f"--since={profile.cutoff}T00:00:00Z",
        "--format=@@%H%x09%cI%x09%s",
        "--name-only",
    ).decode()
    out = []
    for block in log.split("@@")[1:]:
        head, *files = block.strip().split("\n")
        commit, committed, subject = head.split("\t", 2)
        files = [f for f in files if f]
        src = profile.source_files(files)
        if harvest.eligible(subject, committed, src, profile.cutoff) is None and any(
            TEST_RE.match(f) for f in files
        ):
            out.append(commit)
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--want", type=int, default=12)
    args = ap.parse_args()
    harness.use_repo(REPO)
    profile = profiles.get("hermes-agent")

    commits = sorted(eligible_by_metadata(profile))
    random.Random(SEED).shuffle(commits)
    (STUDY / "order.json").write_text(json.dumps(commits, indent=0) + "\n")
    print(f"{len(commits)} commits pass the metadata gates; walking in seeded order", flush=True)

    walk_file = STUDY / "walk.jsonl"
    walked = {}
    if walk_file.is_file():
        for line in walk_file.read_text().splitlines():
            r = json.loads(line)
            walked[r["commit"]] = r
    cands_file = STUDY / "candidates.json"
    found = json.loads(cands_file.read_text()) if cands_file.is_file() else []
    work = Path.home() / "nm-bench" / "harvest-work"
    work.mkdir(parents=True, exist_ok=True)
    # Record what the tests did, so "no FAIL_TO_PASS" can be told apart from
    # "the tests couldn't run in this environment".
    seen: list[dict] = []
    real_run_tests = harness.run_tests

    def recording_run_tests(*a, **k):
        out = real_run_tests(*a, **k)
        seen.append(out)
        return out

    harness.run_tests = recording_run_tests
    for i, commit in enumerate(commits):
        if len(found) >= args.want:
            break
        if commit in walked:
            continue
        seen.clear()
        task = harvest.harvest_one(commit, PYTHON, work, profile)
        rec = {"position": i, "commit": commit, "qualified": bool(task)}
        for name, outcomes in zip(("before", "after"), seen, strict=False):
            counts: dict[str, int] = {}
            for o in outcomes.values():
                counts[o] = counts.get(o, 0) + 1
            rec[name] = counts or "no report"
        if task:
            found.append(task)
            cands_file.write_text(json.dumps(found, indent=2) + "\n")
            rec["f2p"], rec["p2p"] = len(task["fail_to_pass"]), len(task["pass_to_pass"])
        with walk_file.open("a") as fh:
            fh.write(json.dumps(rec) + "\n")
        print(
            f"[{i}] {commit[:10]}: {'QUALIFIED' if task else 'no'} ({len(found)}/{args.want})",
            flush=True,
        )
    print(f"done: {len(found)} candidate(s) in {cands_file}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
