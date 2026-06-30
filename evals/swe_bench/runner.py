"""SWE-bench *retrieval* eval runner — gold-patch-file recall, no LLM agent loop.

    python -m evals.swe_bench.runner --selfcheck          # offline gate (no deps, no net)
    python -m evals.swe_bench.runner --run --limit 20      # real run (clones repos; heavy deps)
    python -m evals.swe_bench.runner --run --dataset princeton-nlp/SWE-bench_Lite --json

What this measures, and what it does **not**
--------------------------------------------
For each SWE-bench task we take the **issue text** (`problem_statement`) and ask:
does NeuralMind's retrieval surface the file(s) the *gold patch* actually edits?
The oracle is objective — the set of files the maintainer's accepted fix touches,
parsed straight from the task's ``patch`` — so there is **no LLM judge** and the
score is deterministic. This is the retrieval analog of SWE-bench, exactly how we
already test NeuralMind's own ``search``/``query`` (gold-file recall@k + MRR).

It is **not** an end-to-end *issue-resolution* solve-rate. Wiring NeuralMind
behind a full coding agent and measuring whether the issue gets fixed is a
separate, opt-in arm that needs an LLM API key; the interface is sketched in
``README.md`` (``--solve``, future) and is deliberately not faked here.

Honesty notes
-------------
* We never hardcode SWE-bench base-commit SHAs or gold files in the repo. The real
  corpus is derived from the **canonical dataset** at ``--run`` time (``datasets``
  / HuggingFace) and gold files are parsed from each task's ``patch``. The only
  committed data is ``fixture.json`` — a tiny **synthetic** set used solely by
  ``--selfcheck`` and the unit test to validate the parser + metric math offline.
* Pure standard library at import time (plus ``neuralmind.quality``, which is
  stdlib-only) so ``--selfcheck`` runs in a minimal environment and gates CI. The
  heavy ``--run`` machinery (``datasets``, ``neuralmind.core``, the
  ``evals.public`` backends) is imported lazily inside ``_run``.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

from neuralmind import quality  # stdlib-only module; safe to import at load time

FIXTURE_PATH = Path(__file__).with_name("fixture.json")
DEFAULT_DATASET = "princeton-nlp/SWE-bench_Lite"
DEFAULT_WORK_DIR = Path(".swe-bench-work")
DEFAULT_OUT = Path("bench/swe_bench")
KS = (1, 3, 5, 8)

# A unified-diff post-image path line: ``+++ b/path/to/file.py`` (optionally with a
# trailing tab + timestamp on non-git diffs). ``/dev/null`` means a deletion.
_PLUS_LINE = re.compile(r"^\+\+\+ (?:b/)?(.+?)(?:\t.*)?$")


def gold_files_from_patch(patch: str) -> list[str]:
    """The basenames of the files a unified-diff ``patch`` edits (post-image).

    Objective oracle: the files the accepted fix touches. We key by **basename**
    to match how the retrieval backends project hits to gold files (see
    ``evals/public/backends.py``). ``/dev/null`` post-images (pure deletions) are
    skipped. Order-preserving and de-duplicated.
    """
    names: list[str] = []
    seen: set[str] = set()
    for line in patch.splitlines():
        m = _PLUS_LINE.match(line)
        if not m:
            continue
        path = m.group(1).strip()
        if not path or path == "/dev/null":
            continue
        name = Path(path).name
        if name and name not in seen:
            seen.add(name)
            names.append(name)
    return names


# --------------------------------------------------------------------------- #
# Offline self-check (dependency-free gate; what CI can run)
# --------------------------------------------------------------------------- #


def load_fixture(path: str | Path = FIXTURE_PATH) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def selfcheck(path: str | Path = FIXTURE_PATH) -> int:
    """Validate the corpus schema, the patch→gold parser, and the metric math
    offline. Returns a process exit code (0 = pass)."""
    failures: list[str] = []
    data = load_fixture(path)
    tasks = data.get("tasks")
    if not isinstance(tasks, list) or not tasks:
        print("FAIL: fixture has no tasks", file=sys.stderr)
        return 1

    required = {"instance_id", "repo", "base_commit", "problem_statement", "patch"}
    for t in tasks:
        missing = required - set(t)
        if missing:
            failures.append(f"{t.get('instance_id', '?')}: missing keys {sorted(missing)}")
            continue
        # The parser must recover the expected gold files from the patch.
        got = gold_files_from_patch(t["patch"])
        want = t.get("expected_gold_files")
        if want is not None and got != want:
            failures.append(f"{t['instance_id']}: gold parse {got} != expected {want}")

    # Metric-math sanity: a perfect ranking scores recall@1 == 1.0 and MRR == 1.0;
    # a gold file at rank 2 scores reciprocal_rank == 0.5. Uses the SAME scorer the
    # real run gates on, so a metric regression is caught here without any network.
    perfect = quality.evaluate_query("m", ["a.py", "b.py"], ["a.py"], ks=KS)
    if perfect.recall.get(1) != 1.0 or perfect.reciprocal_rank != 1.0:
        failures.append("metric: perfect ranking did not score 1.0")
    rank2 = quality.evaluate_query("m", ["x.py", "a.py"], ["a.py"], ks=KS)
    if rank2.reciprocal_rank != 0.5:
        failures.append(f"metric: gold@rank2 MRR {rank2.reciprocal_rank} != 0.5")

    if failures:
        for f in failures:
            print(f"FAIL: {f}", file=sys.stderr)
        return 1
    print(f"selfcheck OK — {len(tasks)} fixture task(s), parser + metric math verified")
    return 0


# --------------------------------------------------------------------------- #
# Real run (off the CI default — clones repos, needs the retrieval stack)
# --------------------------------------------------------------------------- #


def _load_dataset_tasks(dataset: str, limit: int | None) -> list[dict[str, Any]]:
    """Load tasks from the canonical SWE-bench dataset (HuggingFace ``datasets``).

    Returns ``[]`` if ``datasets`` isn't installed or the dataset can't be loaded,
    so the runner skips cleanly rather than inventing data."""
    try:
        from datasets import load_dataset  # type: ignore
    except Exception:
        print(
            "datasets not installed — `pip install datasets` to run against the real "
            "SWE-bench corpus. Skipping (no fabricated tasks).",
            file=sys.stderr,
        )
        return []
    try:
        ds = load_dataset(dataset, split="test")
    except Exception as exc:  # network / auth / unknown dataset
        print(f"could not load dataset {dataset!r}: {exc}", file=sys.stderr)
        return []
    rows = list(ds)
    if limit is not None:
        rows = rows[:limit]
    return rows


def _checkout_task(repo: str, base_commit: str, dest: Path) -> Path | None:
    """Fetch exactly ``base_commit`` of ``github.com/<repo>`` into ``dest``.

    Single-commit fetch (no full history), fail-closed: returns ``None`` on any
    error or if HEAD can't be confirmed at the requested SHA."""
    from evals.public.run import _git, _head  # reuse the public-benchmark git helpers

    url = f"https://github.com/{repo}.git"
    try:
        if not (dest / ".git").exists():
            dest.mkdir(parents=True, exist_ok=True)
            _git(["git", "-C", str(dest), "init", "-q"], timeout=30)
            _git(["git", "-C", str(dest), "remote", "add", "origin", url], timeout=30)
        _git(["git", "-C", str(dest), "fetch", "--depth", "1", "origin", base_commit], timeout=300)
        _git(["git", "-C", str(dest), "checkout", "-q", "FETCH_HEAD"], timeout=60)
    except Exception:
        return None
    return dest if _head(dest) == base_commit else None


def _run(
    dataset: str = DEFAULT_DATASET,
    limit: int | None = None,
    work_dir: Path = DEFAULT_WORK_DIR,
    out: Path | None = DEFAULT_OUT,
) -> dict[str, Any]:
    """Score NeuralMind retrieval over real SWE-bench tasks. Heavy, off-CI."""
    from evals.public import backends  # lazy: pulls neuralmind + tokenizer
    from evals.public.run import _aggregate, _build_nm

    tasks = _load_dataset_tasks(dataset, limit)
    work_dir.mkdir(parents=True, exist_ok=True)
    results: list[Any] = []
    rows: list[dict[str, Any]] = []
    skipped: list[dict[str, str]] = []

    for t in tasks:
        iid = t["instance_id"]
        gold = gold_files_from_patch(t.get("patch", ""))
        if not gold:
            skipped.append({"instance_id": iid, "reason": "no gold files in patch"})
            continue
        src = _checkout_task(t["repo"], t["base_commit"], work_dir / iid)
        if src is None:
            skipped.append({"instance_id": iid, "reason": "checkout unavailable"})
            continue
        nm = _build_nm(src)
        if nm is None:
            skipped.append({"instance_id": iid, "reason": "retrieval stack unavailable"})
            continue
        r = backends.run_neuralmind(iid, t["problem_statement"], gold, nm)
        results.append(r)
        rows.append({"instance_id": iid, "gold_files": gold, **r.to_dict()})

    report = {
        "harness": "swe_bench_retrieval",
        "dataset": dataset,
        "oracle": "gold-patch-files",
        "n_scored": len(results),
        "n_skipped": len(skipped),
        "summary": _aggregate(results) if results else {},
        "tasks": rows,
        "skipped": skipped,
    }
    if out is not None and results:
        out.mkdir(parents=True, exist_ok=True)
        (out / "results.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="SWE-bench retrieval eval for NeuralMind")
    ap.add_argument(
        "--selfcheck", action="store_true", help="offline schema + metric gate (no net)"
    )
    ap.add_argument("--run", action="store_true", help="score retrieval on the real dataset")
    ap.add_argument("--dataset", default=DEFAULT_DATASET, help="HuggingFace dataset id")
    ap.add_argument("--limit", type=int, default=None, help="cap the number of tasks")
    ap.add_argument("--work-dir", default=str(DEFAULT_WORK_DIR))
    ap.add_argument("--out", default=str(DEFAULT_OUT), help="where to write results.json")
    ap.add_argument("--json", action="store_true", help="emit the report as JSON to stdout")
    args = ap.parse_args(argv)

    if args.run:
        report = _run(
            dataset=args.dataset,
            limit=args.limit,
            work_dir=Path(args.work_dir),
            out=Path(args.out) if args.out else None,
        )
        if args.json:
            print(json.dumps(report, indent=2))
        else:
            s = report["summary"]
            print(
                f"SWE-bench retrieval ({report['dataset']}): scored {report['n_scored']}, "
                f"skipped {report['n_skipped']}"
            )
            if s:
                print(
                    f"  mean gold-file recall {s['mean_recall']} · found-rate "
                    f"{s['found_rate']} · MRR {s['mean_mrr']} · median tokens {s['median_tokens']}"
                )
            if report["n_scored"] == 0:
                print("  (no tasks scored — see skip reasons above; needs `datasets` + network)")
        return 0

    # Default to the offline gate (also the `--selfcheck` path).
    return selfcheck()


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
