"""Turn bug-fix commits into benchmark tasks with an objective test oracle.

    python -m evals.task_outcome.harvest --python <venv>/bin/python \\
        --work-dir <scratch> --out <scratch>/candidates.json <commit> [<commit> ...]

For each fix commit C with parent P, the fix's test files are run twice: on P
with C's tests laid over it, and on C itself. A test that passes on C but not
on P is a FAIL_TO_PASS test, the proof that the fix fixed something; a test
that passes on both is PASS_TO_PASS, the proof that nothing else broke. A
commit qualifies when it has at least one FAIL_TO_PASS test and changes source
under ``neuralmind/``.

Each candidate is written with an empty ``prompt``. The prompt, a statement of
the symptom that names no file or function, is written by hand before any agent
runs, and ``tasks.json`` is committed with the pre-registration.
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

from evals.task_outcome import harness


def harvest_one(commit: str, python: str, work: Path) -> dict | None:
    commit = harness.git("rev-parse", commit).decode().strip()
    parent = harness.parent_of(commit)
    src = [
        p
        for p in harness.changed_files(commit)
        if p.startswith("neuralmind/") and p.endswith(".py")
    ]
    tests = harness.test_files_of(commit)
    run_files = [p for p in tests if Path(p).name.startswith("test_") and p.endswith(".py")]
    if not src or not run_files:
        return None

    before_ws = harness.snapshot(parent, work / f"{commit[:10]}-before")
    harness.overlay(commit, tests, before_ws)
    before = harness.run_tests(before_ws, run_files, python)
    after_ws = harness.snapshot(commit, work / f"{commit[:10]}-after")
    after = harness.run_tests(after_ws, run_files, python)
    shutil.rmtree(before_ws, ignore_errors=True)
    shutil.rmtree(after_ws, ignore_errors=True)

    f2p = sorted(t for t, o in after.items() if o == "passed" and before.get(t) != "passed")
    p2p = sorted(t for t, o in after.items() if o == "passed" and before.get(t) == "passed")
    if not f2p:
        return None
    subject = harness.git("log", "-1", "--format=%s", commit).decode().strip()
    return {
        "id": commit[:10],
        "fix_commit": commit,
        "base_commit": parent,
        "subject": subject,
        "gold_files": src,
        "test_files": tests,
        "run_files": run_files,
        "fail_to_pass": f2p,
        "pass_to_pass": p2p,
        "prompt": "",
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("commits", nargs="+")
    ap.add_argument(
        "--python", required=True, help="interpreter with the test deps, no neuralmind installed"
    )
    ap.add_argument("--work-dir", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args(argv)

    args.work_dir.mkdir(parents=True, exist_ok=True)
    found = json.loads(args.out.read_text()) if args.out.is_file() else []
    done = {t["fix_commit"][:10] for t in found}
    for commit in args.commits:
        commit = harness.git("rev-parse", commit).decode().strip()
        if commit[:10] in done:
            continue
        task = harvest_one(commit, args.python, args.work_dir)
        status = (
            f"{len(task['fail_to_pass'])} F2P, {len(task['pass_to_pass'])} P2P"
            if task
            else "skipped"
        )
        print(f"{commit[:10]}: {status}", flush=True)
        if task:
            found.append(task)
            args.out.write_text(json.dumps(found, indent=2) + "\n")
    print(f"{len(found)} candidate task(s) in {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
