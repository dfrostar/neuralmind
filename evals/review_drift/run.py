"""Run `neuralmind review` and `neuralmind drift` over the selected commits.

For every parent commit in ``sets.json`` the clone is checked out there, its
``.neuralmind/`` removed, and ``neuralmind build .`` run: a cold index, holding
only the seeds the build writes. Then, per the spec:

- **review**, for each commit in the review set and each ground-truth file
  held out in turn: the other files take the commit's version, ``neuralmind
  review . --json --top-k 10`` runs, and the held-out file's rank is recorded
  beside the two baselines' ranks on the same pair (git co-change over the
  300 commits before the parent; structural adjacency from the built graph).
- **drift**, for each commit in the fix and control sets: with the tree at
  the parent, ``neuralmind drift . --json --diff <commit>`` examines the
  pre-fix symbols the commit's hunks touch.

``--hermes`` runs the drift arm on the hermes-agent task files instead,
with the cached index at each task's base commit symlinked in.

Records go to ``records.jsonl`` as they are produced; a rerun skips parents
already recorded, so an interrupted run resumes. Heavy: run it under the
machine's heavy-job lock, one at a time.
"""

from __future__ import annotations

import argparse
import collections
import json
import os
import shutil
import sqlite3
import subprocess
import sys
import time
from pathlib import Path

from evals.review_drift.select import is_test_path

TOP_K = 10
COCHANGE_WINDOW = 300
ADJACENT_EDGE_TYPES = ("call", "import", "inherits")


# --------------------------------------------------------------------- #
# git helpers
# --------------------------------------------------------------------- #


def git(repo: Path, *args: str, check: bool = True) -> str:
    return subprocess.run(
        ["git", "-C", str(repo), *args],
        check=check,
        capture_output=True,
        text=True,
        errors="replace",
    ).stdout


def checkout(repo: Path, ref: str) -> None:
    git(repo, "checkout", "-q", "--force", ref)
    git(repo, "clean", "-fdq", "-e", ".neuralmind")


def modified_files(repo: Path, parent: str, commit: str) -> list[str]:
    """Files that exist at both ends and changed: added, deleted and renamed
    files can't be named by an index built at the parent."""
    out = git(repo, "diff", "--name-status", "--no-renames", parent, commit)
    return [line.split("\t", 1)[1] for line in out.splitlines() if line.startswith("M\t")]


def cochange_ranking(repo: Path, parent: str, seeds: set[str], candidates: set[str]) -> list[str]:
    """Candidates ranked by how many of the ``COCHANGE_WINDOW`` non-merge
    commits before ``parent`` changed both them and a seed; ties go to the
    most recent such commit. Candidates never co-changed are left out."""
    out = git(
        repo,
        "log",
        f"{parent}^",
        "--no-merges",
        f"-n{COCHANGE_WINDOW}",
        "--format=@%H",
        "--name-only",
        check=False,
    )
    score: dict[str, int] = collections.Counter()
    recency: dict[str, int] = {}
    index = 0
    files: list[str] = []

    def flush() -> None:
        nonlocal index
        if files and seeds.intersection(files):
            for f in set(files):
                if f in candidates:
                    score[f] += 1
                    recency.setdefault(f, index)
        index += 1
        files.clear()

    for line in out.splitlines():
        if line.startswith("@"):
            flush()
        elif line.strip():
            files.append(line.strip())
    flush()
    # The path is the last key: without it, candidates tied on count and
    # recency kept the order of a set iteration, which varies with the hash
    # seed, and a published rank must not.
    return sorted(score, key=lambda f: (-score[f], recency[f], f))


# --------------------------------------------------------------------- #
# the built index
# --------------------------------------------------------------------- #


def graph_files(repo: Path) -> dict[str, str]:
    """``node id -> source_file`` for the graph the build wrote."""
    graph = json.loads((repo / ".neuralmind" / "graph.json").read_text())
    nodes = graph["nodes"]
    if isinstance(nodes, dict):
        nodes = list(nodes.values())
    return {str(n["id"]): n["source_file"] for n in nodes if n.get("source_file")}


def adjacency_ranking(
    repo: Path, node_file: dict[str, str], seeds: set[str], candidates: set[str]
) -> list[str]:
    """Candidates ranked by the number of call/import/inherits edges between
    their symbols and the seeds' symbols, either direction."""
    conn = sqlite3.connect(str(repo / ".neuralmind" / "synapses.db"))
    placeholders = ",".join("?" for _ in ADJACENT_EDGE_TYPES)
    rows = conn.execute(
        f"select caller, callee from structural_edges where edge_type in ({placeholders})",
        ADJACENT_EDGE_TYPES,
    ).fetchall()
    conn.close()
    score: dict[str, int] = collections.Counter()
    for a, b in rows:
        fa, fb = node_file.get(a), node_file.get(b)
        if not fa or not fb or fa == fb:
            continue
        if fa in seeds and fb in candidates:
            score[fb] += 1
        if fb in seeds and fa in candidates:
            score[fa] += 1
    return sorted(score, key=lambda f: (-score[f], f))


def rank_of(target: str, ranking: list[str]) -> int | None:
    try:
        return ranking.index(target) + 1
    except ValueError:
        return None


# --------------------------------------------------------------------- #
# the commands under test
# --------------------------------------------------------------------- #


def run_cli(binary: str, repo: Path, *args: str) -> tuple[dict | None, float, str, int]:
    env = {k: v for k, v in os.environ.items() if not k.startswith("NEURALMIND_")}
    started = time.perf_counter()
    proc = subprocess.run([binary, *args], cwd=str(repo), capture_output=True, text=True, env=env)
    elapsed = time.perf_counter() - started
    text = proc.stdout.strip()
    try:
        # The CLI may print a stale-index notice before the JSON.
        payload = json.loads(text[text.index("{") :]) if "{" in text else None
    except (ValueError, json.JSONDecodeError):
        payload = None
    return payload, elapsed, (proc.stderr or "")[-2000:], proc.returncode


def build(binary: str, repo: Path) -> dict:
    shutil.rmtree(repo / ".neuralmind", ignore_errors=True)
    payload, elapsed, err, _code = run_cli(binary, repo, "build", ".", "--json")
    ok = (repo / ".neuralmind" / "graph.json").exists() and (
        repo / ".neuralmind" / "synapses.db"
    ).exists()
    conn = sqlite3.connect(str(repo / ".neuralmind" / "synapses.db")) if ok else None
    namespaces = (
        dict(conn.execute("select namespace, count(*) from synapses group by namespace").fetchall())
        if conn
        else {}
    )
    if conn:
        conn.close()
    return {
        "ok": ok,
        "elapsed_s": round(elapsed, 2),
        "synapse_namespaces": namespaces,
        "stderr": err if not ok else "",
    }


def review_pairs(
    binary: str, repo: Path, name: str, entry: dict, node_file: dict[str, str]
) -> list[dict]:
    parent, commit = entry["parent"], entry["commit"]
    indexed = set(node_file.values())
    truth = [f for f in modified_files(repo, parent, commit) if f in indexed]
    records: list[dict] = [
        {
            "kind": "review_commit",
            "repo": name,
            "commit": commit,
            "parent": parent,
            "subject": entry["subject"],
            "changed_files": entry["changed_files"],
            "ground_truth": truth,
            "n_indexed_files": len(indexed),
            "dropped": len(truth) < 2,
        }
    ]
    if len(truth) < 2:
        return records
    for held in truth:
        seeds = [f for f in truth if f != held]
        git(repo, "checkout", commit, "--", *seeds)
        payload, elapsed, err, code = run_cli(
            binary, repo, "review", ".", "--json", "--top-k", str(TOP_K)
        )
        if code != 0 or payload is None or "at_risk" not in payload:
            # A failed call is not a miss. Stop here; the parent never reaches
            # parent_done, and the resume drops its partial records.
            git(repo, "checkout", parent, "--", *seeds)
            raise RuntimeError(f"review failed on {commit[:10]} ({code}): {err.strip()[-500:]}")
        git(repo, "checkout", parent, "--", *seeds)
        at_risk = [item["file"] for item in (payload or {}).get("at_risk", [])]
        seed_set = set(seeds)
        candidates = indexed - seed_set
        records.append(
            {
                "kind": "review_pair",
                "repo": name,
                "commit": commit,
                "parent": parent,
                "held_out": held,
                "seeds": seeds,
                "n_candidates": len(candidates),
                "review_list": at_risk,
                "rank_review": rank_of(held, at_risk),
                "test_entries": sum(1 for f in at_risk if is_test_path(f)),
                "rank_cochange": rank_of(
                    held, cochange_ranking(repo, parent, seed_set, candidates)
                ),
                "rank_adjacency": rank_of(
                    held, adjacency_ranking(repo, node_file, seed_set, candidates)
                ),
                "elapsed_s": round(elapsed, 2),
            }
        )
    return records


def drift_record(
    binary: str, repo: Path, name: str, which: str, entry: dict, gold: list[str] | None = None
) -> dict:
    payload, elapsed, err, code = run_cli(
        binary, repo, "drift", ".", "--json", "--diff", entry["commit"]
    )
    if code != 0 or payload is None or "findings" not in payload:
        raise RuntimeError(f"drift failed on {entry['commit'][:10]} ({code}): {err.strip()[-500:]}")
    findings = payload.get("findings", [])
    return {
        "kind": "drift",
        "repo": name,
        "set": which,
        "commit": entry["commit"],
        "parent": entry["parent"],
        "subject": entry.get("subject", ""),
        "source_files": entry.get("source_files", gold or []),
        "findings": findings,
        "n_findings": len(findings),
        "symbols_checked": payload.get("symbols_checked"),
        # Empty when the commit only added lines: zero-length hunks on the
        # parent's side give drift no symbol to examine (spec, endpoints).
        "changed_files": payload.get("changed_files", []),
        "graph": payload.get("graph"),
        "elapsed_s": round(elapsed, 2),
    }


# --------------------------------------------------------------------- #
# drivers
# --------------------------------------------------------------------- #


def tool_identity(binary: str) -> dict:
    """Which NeuralMind the binary actually runs.

    Resolved from ``/``, never from the repository: run from the checkout, a
    ``python -c`` import finds the checkout through the current directory and
    hides a wheel installed in the venv. The first run of this eval was
    discarded for exactly that (the venv ran PyPI 4.21.0 while the check said
    "the checkout"), so the result also says whether the module is an
    installed copy or a checkout with a commit.
    """
    version = subprocess.run(
        [binary, "--version"], capture_output=True, text=True, cwd="/"
    ).stdout.strip()
    module = subprocess.run(
        [
            str(Path(binary).parent / "python"),
            "-c",
            "import neuralmind; print(neuralmind.__file__)",
        ],
        capture_output=True,
        text=True,
        cwd="/",
    ).stdout.strip()
    installed = "site-packages" in module
    checkout_dir = None if installed or not module else Path(module).parents[1]
    commit = git(checkout_dir, "rev-parse", "HEAD", check=False).strip() if checkout_dir else ""
    identity = {
        "binary": binary,
        "version": version,
        "module": module,
        "installed_copy": installed,
        "checkout_commit": commit,
    }
    print(f"tool: {version} from {module}" + (f" at {commit[:10]}" if commit else ""), flush=True)
    return identity


def load_records(records_path: Path) -> list[dict]:
    if not records_path.exists():
        return []
    return [json.loads(line) for line in records_path.read_text().splitlines() if line.strip()]


def write_records(records_path: Path, records: list[dict]) -> None:
    records_path.write_text("".join(json.dumps(r) + "\n" for r in records))


def done_parents(records_path: Path) -> set[tuple[str, str]]:
    return {
        (r["repo"], r["parent"])
        for r in load_records(records_path)
        if r.get("kind") == "parent_done"
    }


def prune_incomplete(records_path: Path) -> int:
    """Drop the records of parents that never reached ``parent_done``.

    A run interrupted mid-parent would otherwise keep that parent's partial
    review and drift records and, on resume, append a second full set, which
    ``analyze`` would count twice. Returns the number of records dropped.
    """
    records = load_records(records_path)
    done = {(r["repo"], r["parent"]) for r in records if r.get("kind") == "parent_done"}
    kept = [
        r
        for r in records
        if r.get("kind") in ("run_start", "parent_done")
        or "parent" not in r
        or (r["repo"], r["parent"]) in done
    ]
    if len(kept) != len(records):
        write_records(records_path, kept)
    return len(records) - len(kept)


def run_public(args: argparse.Namespace) -> int:
    sets = json.loads(Path(args.sets).read_text())
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    records_path = out / "records.jsonl"
    dropped = prune_incomplete(records_path)
    if dropped:
        print(f"resume: dropped {dropped} record(s) of an unfinished parent", flush=True)
    done = done_parents(records_path)
    with records_path.open("a") as fh:

        def emit(record: dict) -> None:
            fh.write(json.dumps(record) + "\n")
            fh.flush()

        emit(
            {
                "kind": "run_start",
                "ts": time.time(),
                "tool": tool_identity(args.neuralmind),
                "sets": args.sets,
            }
        )
        for name, repo_info in sets["repos"].items():
            if args.repo and name not in args.repo:
                continue
            repo = Path(repo_info["path"])
            by_parent: dict[str, dict[str, list[dict]]] = collections.defaultdict(
                lambda: {"review": [], "fix": [], "control": []}
            )
            for which in ("review", "fix", "control"):
                for entry in repo_info[which]:
                    by_parent[entry["parent"]][which].append(entry)
            for parent, groups in by_parent.items():
                if (name, parent) in done:
                    continue
                checkout(repo, parent)
                built = build(args.neuralmind, repo)
                emit({"kind": "build", "repo": name, "parent": parent, **built})
                if not built["ok"]:
                    emit(
                        {
                            "kind": "parent_done",
                            "repo": name,
                            "parent": parent,
                            "skipped": "build failed",
                        }
                    )
                    continue
                node_file = graph_files(repo)
                for entry in groups["review"]:
                    for record in review_pairs(args.neuralmind, repo, name, entry, node_file):
                        emit(record)
                checkout(repo, parent)
                for which in ("fix", "control"):
                    for entry in groups[which]:
                        emit(drift_record(args.neuralmind, repo, name, which, entry))
                emit({"kind": "parent_done", "repo": name, "parent": parent})
                print(f"{name} {parent[:10]}: done ({built['elapsed_s']} s build)", flush=True)
            checkout(repo, repo_info["pinned"])
    return 0


def rescore_baselines(args: argparse.Namespace) -> int:
    """Recompute the two baselines' ranks for every recorded review pair.

    Rebuilds the index at each parent (the candidate set is the files it
    holds) but makes no ``review`` or ``drift`` call, so the published review
    ranks stay as recorded; only ``rank_cochange`` and ``rank_adjacency`` are
    rewritten in place. Used after the co-change sort gained its deterministic
    tie-break.
    """
    sets = json.loads(Path(args.sets).read_text())
    records_path = Path(args.out) / "records.jsonl"
    records = load_records(records_path)
    by_parent: dict[tuple[str, str], list[dict]] = collections.defaultdict(list)
    for r in records:
        if r.get("kind") == "review_pair":
            by_parent[(r["repo"], r["parent"])].append(r)
    changed = 0
    for (name, parent), pairs in by_parent.items():
        repo = Path(sets["repos"][name]["path"])
        checkout(repo, parent)
        built = build(args.neuralmind, repo)
        if not built["ok"]:
            print(f"{name} {parent[:10]}: build failed, ranks left as recorded", flush=True)
            continue
        node_file = graph_files(repo)
        indexed = set(node_file.values())
        for p in pairs:
            seed_set = set(p["seeds"])
            candidates = indexed - seed_set
            before = (p["rank_cochange"], p["rank_adjacency"])
            p["rank_cochange"] = rank_of(
                p["held_out"], cochange_ranking(repo, parent, seed_set, candidates)
            )
            p["rank_adjacency"] = rank_of(
                p["held_out"], adjacency_ranking(repo, node_file, seed_set, candidates)
            )
            p["n_candidates"] = len(candidates)
            changed += before != (p["rank_cochange"], p["rank_adjacency"])
        print(f"{name} {parent[:10]}: rescored {len(pairs)} pair(s)", flush=True)
    for _name, repo_info in sets["repos"].items():
        checkout(Path(repo_info["path"]), repo_info["pinned"])
    records.append(
        {
            "kind": "rescore",
            "ts": time.time(),
            "tool": tool_identity(args.neuralmind),
            "pairs_changed": changed,
        }
    )
    write_records(records_path, records)
    print(f"rescored: {changed} pair(s) changed a baseline rank", flush=True)
    return 0


def run_hermes(args: argparse.Namespace) -> int:
    """Drift only, on the task-outcome tasks whose indexes are cached."""
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    records_path = out / "records.jsonl"
    repo = Path(args.hermes_clone)
    dropped = prune_incomplete(records_path)
    if dropped:
        print(f"resume: dropped {dropped} record(s) of an unfinished parent", flush=True)
    done = done_parents(records_path)
    tasks: list[tuple[str, dict]] = []
    for tasks_file in args.hermes_tasks:
        for t in json.loads(Path(tasks_file).read_text()):
            tasks.append((tasks_file, t))
    link = repo / ".neuralmind"
    with records_path.open("a") as fh:

        def emit(record: dict) -> None:
            fh.write(json.dumps(record) + "\n")
            fh.flush()

        emit(
            {
                "kind": "run_start",
                "ts": time.time(),
                "tool": tool_identity(args.neuralmind),
                "hermes_tasks": args.hermes_tasks,
            }
        )
        for tasks_file, t in tasks:
            if ("hermes-agent", t["base_commit"]) in done:
                continue
            cached = None
            for root in args.hermes_index:
                # Resolved: the link lives in the clone, so a relative root
                # would otherwise resolve against the clone and dangle.
                candidate = (Path(root).expanduser() / t["id"] / ".neuralmind").resolve()
                if candidate.exists():
                    cached = candidate
                    break
            if cached is None:
                emit(
                    {
                        "kind": "parent_done",
                        "repo": "hermes-agent",
                        "parent": t["base_commit"],
                        "skipped": f"no cached index for {t['id']}",
                    }
                )
                continue
            if link.is_symlink() or link.exists():
                if link.is_symlink():
                    link.unlink()
                else:
                    shutil.move(str(link), str(link) + ".moved-aside")
            checkout(repo, t["base_commit"])
            link.symlink_to(cached)
            entry = {
                "commit": t["fix_commit"],
                "parent": t["base_commit"],
                "subject": t.get("subject", ""),
                "source_files": t.get("gold_files", []),
            }
            record = drift_record(
                args.neuralmind, repo, "hermes-agent", "fix", entry, gold=t.get("gold_files")
            )
            record["task_id"] = t["id"]
            record["tasks_file"] = tasks_file
            emit(record)
            emit({"kind": "parent_done", "repo": "hermes-agent", "parent": t["base_commit"]})
            print(
                f"hermes-agent {t['id']}: {record['n_findings']} finding(s), {record['symbols_checked']} symbols, {record['elapsed_s']} s",
                flush=True,
            )
            link.unlink()
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument(
        "--neuralmind",
        required=True,
        help="the neuralmind binary under test (a venv's bin/neuralmind)",
    )
    ap.add_argument("--out", required=True, help="results directory; records.jsonl is appended")
    ap.add_argument("--sets", help="sets.json from select (public repositories)")
    ap.add_argument("--repo", action="append", help="limit to these manifest repo names")
    ap.add_argument(
        "--hermes", action="store_true", help="drift arm on the hermes-agent tasks instead"
    )
    ap.add_argument(
        "--rescore-baselines",
        action="store_true",
        help="recompute co-change and adjacency ranks for recorded review pairs; no review/drift calls",
    )
    ap.add_argument("--hermes-clone", help="hermes-agent clone holding the tasks' commits")
    ap.add_argument(
        "--hermes-tasks", action="append", default=[], help="tasks.json files (held-out, screen)"
    )
    ap.add_argument(
        "--hermes-index",
        action="append",
        default=[],
        help="directories holding <task id>/.neuralmind caches",
    )
    args = ap.parse_args(argv)
    if args.rescore_baselines:
        if not args.sets:
            ap.error("--rescore-baselines needs --sets")
        return rescore_baselines(args)
    if args.hermes:
        if not (args.hermes_clone and args.hermes_tasks and args.hermes_index):
            ap.error("--hermes needs --hermes-clone, --hermes-tasks and --hermes-index")
        return run_hermes(args)
    if not args.sets:
        ap.error("--sets is required unless --hermes")
    return run_public(args)


if __name__ == "__main__":
    sys.exit(main())
