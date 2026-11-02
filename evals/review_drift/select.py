"""Pick the commits the review/drift eval runs on, mechanically.

For each public-benchmark repository (``evals/public/manifest.json``), walk
back from its pinned commit over at most ``--window`` non-merge commits and
take, most recent first:

- the **review set**: commits that changed 2 to 6 source ``.py`` files under
  the manifest's subdir (tests not counted), capped at ``--cap``;
- the **fix set**: commits whose subject matches ``fix|bug|regress`` and
  changed 1 to 6 source files, capped at ``--cap``;
- the **control set**: as many non-matching commits with 1 to 6 source files.

Nothing reads a commit's content here. The output names the clone, the pinned
commit and each commit's hash, parent and changed files, so ``run`` needs no
further selection. Changing the rules after a run goes in the spec's change
log.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path

MANIFEST = Path(__file__).resolve().parents[1] / "public" / "manifest.json"
FIX_SUBJECT = re.compile(r"fix|bug|regress", re.IGNORECASE)


def is_test_path(path: str) -> bool:
    parts = path.split("/")
    return (
        parts[0] in ("tests", "test")
        or "/tests/" in path
        or "/test/" in path
        or os.path.basename(path).startswith("test_")
        or os.path.basename(path).endswith("_test.py")
    )


def source_files(changed: list[str], subdir: str) -> list[str]:
    prefix = subdir.rstrip("/") + "/"
    return [
        p for p in changed if p.startswith(prefix) and p.endswith(".py") and not is_test_path(p)
    ]


def walk_commits(repo: Path, start: str, window: int) -> list[dict]:
    """``[{"commit", "parent", "subject", "files"}, ...]`` most recent first.

    One ``git log`` with a marker line per commit; ``--name-only`` lists the
    changed paths after it. Root commits (no parent) are skipped.
    """
    out = subprocess.check_output(
        [
            "git",
            "-C",
            str(repo),
            "log",
            start,
            "--no-merges",
            f"-n{window}",
            "--format=@%H %P|%s",
            "--name-only",
        ],
        text=True,
        errors="replace",
    )
    commits: list[dict] = []
    cur: dict | None = None
    for line in out.splitlines():
        if line.startswith("@"):
            head, subject = line[1:].split("|", 1)
            parts = head.split()
            cur = {
                "commit": parts[0],
                "parent": parts[1] if len(parts) > 1 else None,
                "subject": subject.strip(),
                "files": [],
            }
            commits.append(cur)
        elif line.strip() and cur is not None:
            cur["files"].append(line.strip())
    return [c for c in commits if c["parent"]]


def select_sets(commits: list[dict], subdir: str, cap: int) -> dict:
    review, fix, control = [], [], []
    for c in commits:
        src = source_files(c["files"], subdir)
        entry = {
            "commit": c["commit"],
            "parent": c["parent"],
            "subject": c["subject"],
            "source_files": src,
            "changed_files": c["files"],
        }
        if 2 <= len(src) <= 6 and len(review) < cap:
            review.append(entry)
        if 1 <= len(src) <= 6:
            if FIX_SUBJECT.search(c["subject"]):
                if len(fix) < cap:
                    fix.append(entry)
            elif len(control) < cap:
                control.append(entry)
    # The control set is "as many as the fix set", most recent first.
    control = control[: len(fix)]
    return {"review": review, "fix": fix, "control": control}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument(
        "--repos",
        required=True,
        help="directory holding one clone per manifest repo, named as in the manifest",
    )
    ap.add_argument("--out", required=True, help="where to write sets.json")
    ap.add_argument("--window", type=int, default=600)
    ap.add_argument("--cap", type=int, default=40)
    ap.add_argument("--manifest", default=str(MANIFEST))
    args = ap.parse_args(argv)

    manifest = json.loads(Path(args.manifest).read_text())
    repos_dir = Path(args.repos).resolve()
    result = {
        "spec": "docs/specs/REVIEW-DRIFT-EVAL-SPEC.md",
        "window": args.window,
        "cap": args.cap,
        "repos": {},
    }
    for entry in manifest["repos"]:
        name = entry["name"]
        clone = repos_dir / name
        if not (clone / ".git").exists():
            print(f"select: no clone at {clone}", file=sys.stderr)
            return 1
        pinned = entry["commit"]
        subprocess.run(
            ["git", "-C", str(clone), "cat-file", "-e", f"{pinned}^{{commit}}"], check=True
        )
        commits = walk_commits(clone, pinned, args.window)
        sets = select_sets(commits, entry["subdir"], args.cap)
        result["repos"][name] = {
            "path": str(clone),
            "pinned": pinned,
            "subdir": entry["subdir"],
            "commits_walked": len(commits),
            **sets,
        }
        print(
            f"{name}: walked {len(commits)}; review {len(sets['review'])}, "
            f"fix {len(sets['fix'])}, control {len(sets['control'])}"
        )
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(result, indent=1) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
