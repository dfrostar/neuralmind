#!/usr/bin/env python3
"""Gate: a fresh public-benchmark run agrees with the committed one.

``bench-public-drift.yml`` regenerates the public benchmark and runs this
against the numbers committed in ``bench/public/results.json`` — the same
file ``tests/test_site_claims.py`` treats as canon. ``docs/benchmarks/public.md``
is the human-readable copy of that file; this script never parses it.

Per repo and backend it compares gold-file recall (tolerance: 5 percentage
points, absolute) and mean tokens per query (tolerance: 10% of the committed
mean, relative). Exit 0 = both runs measured the same (repo, backend) pairs
and every one is within tolerance. Exit 1 = drift, a committed number the
fresh run did not produce, a fresh number the committed run does not publish,
or no committed numbers at all.

The inline parser this replaced read ``public.md`` with regexes that never
matched its format, found nothing, printed a warning, and exited 0, so drift
was never detected. Finding nothing to compare is a failure here, not a pass.

    python scripts/check_public_bench_drift.py --fresh public-report.json \\
        --committed committed-results.json
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
COMMITTED = ROOT / "bench" / "public" / "results.json"

RECALL_TOLERANCE = 0.05  # absolute: 5 percentage points of gold-file recall
COST_TOLERANCE = 0.10  # relative: 10% of the committed mean tokens/query
# Recall values are 4-decimal fractions, so 0.85 vs 0.90 must not trip on float error.
_EPSILON = 1e-9

REGENERATE = """
If the change is intended, regenerate the snapshot from a clean work dir. An
existing .bench-work keeps its index between runs and updates it incrementally,
so after an indexing change it can produce numbers that a clean build, which is
what CI runs, does not:

    rm -rf .bench-work && python -m evals.public.run --out bench/public

Commit bench/public/ in the same PR as the matching docs/benchmarks/public.md
tables and site/claims.json figures. tests/test_public_md_matches_results.py
and tests/test_site_claims.py check both against bench/public/results.json.
In CI, this run's fresh results are uploaded as the public-benchmark-drift
artifact."""

Numbers = dict[str, dict[str, dict[str, float]]]


def extract(report: dict) -> Numbers:
    """``{repo: {backend: {"recall", "tokens"}}}`` from a ``run.py`` report.

    A repo the run skipped (no checkout) has no ``summary`` and contributes
    nothing, so it surfaces as missing rather than as a pass.
    """
    numbers: Numbers = {}
    for repo in report.get("repos", []):
        for backend, stats in (repo.get("summary") or {}).items():
            numbers.setdefault(repo["name"], {})[backend] = {
                "recall": float(stats["mean_recall"]),
                "tokens": float(stats["mean_tokens"]),
            }
    return numbers


def load(path: Path) -> Numbers:
    return extract(json.loads(path.read_text(encoding="utf-8")))


def compare(
    fresh: Numbers,
    committed: Numbers,
    recall_tolerance: float = RECALL_TOLERANCE,
    cost_tolerance: float = COST_TOLERANCE,
) -> tuple[list[str], list[str]]:
    """Return ``(ok, failures)``, one line per (repo, backend) in either run.

    A (repo, backend) in only one run is a failure. Only committed: the fresh
    run didn't re-measure a published number (e.g. its checkout was skipped).
    Only fresh: the benchmark measures something the snapshot doesn't publish
    (e.g. a repo was added to the manifest without regenerating results.json).
    """
    ok: list[str] = []
    failures: list[str] = []
    pairs = {(repo, backend) for run in (committed, fresh) for repo in run for backend in run[repo]}
    for repo, backend in sorted(pairs):
        c = committed.get(repo, {}).get(backend)
        f = fresh.get(repo, {}).get(backend)
        label = f"{repo}/{backend}"
        if f is None:
            failures.append(f"{label}: committed but missing from the fresh run")
            continue
        if c is None:
            failures.append(f"{label}: in the fresh run but not in the committed snapshot")
            continue
        recall_delta = f["recall"] - c["recall"]
        cost_delta = f["tokens"] - c["tokens"]
        if c["tokens"]:
            cost_ratio = cost_delta / c["tokens"]
        else:
            cost_ratio = 0.0 if not cost_delta else float("inf")
        line = (
            f"{label}: recall {f['recall']:.4f} vs committed {c['recall']:.4f} "
            f"(Δ{recall_delta:+.4f}), tokens {f['tokens']:.1f} vs committed "
            f"{c['tokens']:.1f} (Δ{cost_ratio:+.1%})"
        )
        drifted = (
            abs(recall_delta) > recall_tolerance + _EPSILON
            or abs(cost_ratio) > cost_tolerance + _EPSILON
        )
        (failures if drifted else ok).append(line)
    return ok, failures


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--fresh", required=True, type=Path, help="report from evals.public.run --json")
    ap.add_argument(
        "--committed",
        default=COMMITTED,
        type=Path,
        help="committed results.json to compare against (default: bench/public/results.json)",
    )
    args = ap.parse_args(argv)

    committed = load(args.committed)
    if not committed:
        print(f"ERROR: no committed per-repo numbers found in {args.committed}")
        return 1
    fresh = load(args.fresh)

    ok, failures = compare(fresh, committed)
    for line in ok:
        print(f"  OK     {line}")
    if failures:
        print(
            f"\nDRIFT DETECTED (tolerance: recall ±{RECALL_TOLERANCE:.2f}, "
            f"tokens ±{COST_TOLERANCE:.0%}):"
        )
        for line in failures:
            print(f"  {line}")
        print(REGENERATE)
        return 1
    print(f"\nAll {len(ok)} committed (repo, backend) numbers within tolerance.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
