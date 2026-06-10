"""Quality eval runner: suite registry, validation, and CLI (PRD 2).

Split from the heavy retrieval path (``harness.py``) so ``--selfcheck`` stays
dependency-free — it validates the golden suites and the metric math without
importing the embedding stack, exactly like the faithfulness eval's selfcheck.

Golden suites reuse the committed polyglot benchmark query sets
(``tests/fixtures/benchmark_queries*.json``), each paired with its fixture
repo. Every query carries ``expected_modules`` — the relevant set the metrics
score retrieval against.
"""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]

# suite name → (fixture repo, golden query file). The query files already exist
# and are used by the self-benchmark; we reuse them so the golden labels have a
# single source of truth.
SUITES: dict[str, dict[str, str]] = {
    "python": {
        "fixture": "tests/fixtures/sample_project",
        "queries": "tests/fixtures/benchmark_queries.json",
    },
    "typescript": {
        "fixture": "tests/fixtures/sample_project_ts",
        "queries": "tests/fixtures/benchmark_queries_ts.json",
    },
    "go": {
        "fixture": "tests/fixtures/sample_project_go",
        "queries": "tests/fixtures/benchmark_queries_go.json",
    },
}


@dataclass
class Query:
    id: str
    question: str
    shape: str
    expected_modules: list[str]


@dataclass
class Suite:
    name: str
    fixture_dir: Path
    queries: list[Query]

    def __len__(self) -> int:
        return len(self.queries)


def load_suite(name: str) -> Suite:
    """Load + lightly validate one golden suite.

    Raises ``ValueError`` for an unknown suite or a malformed query set.
    """
    if name not in SUITES:
        raise ValueError(f"unknown suite {name!r}; known: {', '.join(sorted(SUITES))}")
    spec = SUITES[name]
    queries_path = _REPO_ROOT / spec["queries"]
    fixture_dir = _REPO_ROOT / spec["fixture"]
    if not queries_path.exists():
        raise ValueError(f"suite {name!r}: query set not found at {queries_path}")

    raw = json.loads(queries_path.read_text(encoding="utf-8"))
    queries: list[Query] = []
    for i, q in enumerate(raw.get("queries", [])):
        for key in ("id", "question", "expected_modules"):
            if key not in q:
                raise ValueError(f"suite {name!r} query #{i} missing required field {key!r}")
        if not q["expected_modules"]:
            raise ValueError(f"suite {name!r} query {q['id']!r} has empty expected_modules")
        queries.append(
            Query(
                id=q["id"],
                question=q["question"],
                shape=q.get("shape", "unknown"),
                expected_modules=list(q["expected_modules"]),
            )
        )
    if not queries:
        raise ValueError(f"suite {name!r}: no queries found in {queries_path}")
    return Suite(name=name, fixture_dir=fixture_dir, queries=queries)


def all_suites() -> list[str]:
    return sorted(SUITES)


def total_query_count() -> int:
    return sum(len(load_suite(name)) for name in SUITES)


# --------------------------------------------------------------------------- #
# Self-check (dependency-free)
# --------------------------------------------------------------------------- #


def _selfcheck() -> int:
    """Validate every golden suite + the metric math, with no heavy deps."""
    from neuralmind import quality

    print("quality eval selfcheck")
    print("=" * 60)
    total = 0
    for name in all_suites():
        try:
            suite = load_suite(name)
        except ValueError as exc:
            print(f"  [FAIL] {name}: {exc}")
            return 1
        fixture_ok = suite.fixture_dir.exists()
        marker = "ok" if fixture_ok else "WARN (fixture dir missing)"
        print(f"  [{marker}] {name}: {len(suite)} queries, fixture {suite.fixture_dir.name}")
        total += len(suite)

    # PRD target: at least 25 golden queries across 3+ repos.
    print("-" * 60)
    print(f"  suites: {len(SUITES)}  total queries: {total}")
    if len(SUITES) < 3:
        print(f"  [FAIL] expected >=3 suites, found {len(SUITES)}")
        return 1
    if total < 25:
        print(f"  [FAIL] expected >=25 golden queries, found {total}")
        return 1

    # Metric sanity: a perfect ranking scores 1.0, a miss scores 0.0.
    perfect = quality.evaluate_query("p", ["a"], ["a"])
    miss = quality.evaluate_query("m", ["x"], ["a"])
    if perfect.reciprocal_rank != 1.0 or miss.reciprocal_rank != 0.0:
        print("  [FAIL] metric self-test: reciprocal_rank is wrong")
        return 1
    agg = quality.aggregate("s", [perfect, miss])
    if abs(agg.mrr - 0.5) > 1e-9:
        print("  [FAIL] metric self-test: MRR aggregation is wrong")
        return 1

    print("  [ok] metric self-test passed")
    print("PASS")
    return 0


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #


def _arg_value(argv: list[str], flag: str) -> str | None:
    if flag in argv:
        i = argv.index(flag)
        if i + 1 < len(argv):
            return argv[i + 1]
    return None


def _run(argv: list[str]) -> int:
    """Run the retrieval-backed quality eval. Degrades to selfcheck if the
    embedding stack or a built index is unavailable."""
    try:
        from . import harness
    except Exception as exc:  # pragma: no cover - import wiring
        print(f"could not import quality harness: {exc}", file=sys.stderr)
        return 2

    suite_name = _arg_value(argv, "--suite")
    baseline_path = _arg_value(argv, "--baseline")
    as_json = "--json" in argv
    names = [suite_name] if suite_name else all_suites()

    baseline = None
    if baseline_path:
        baseline = json.loads(Path(baseline_path).read_text(encoding="utf-8"))

    try:
        reports = [harness.run_suite(name) for name in names]
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    except RuntimeError as exc:
        print(f"quality A/B unavailable: {exc}", file=sys.stderr)
        print(
            "It needs the retrieval stack + built fixtures. Use --selfcheck to "
            "validate the golden suites + metric math only.",
            file=sys.stderr,
        )
        return 2

    return harness.emit(reports, baseline=baseline, as_json=as_json)


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if "--selfcheck" in argv:
        return _selfcheck()
    if "--list" in argv:
        for name in all_suites():
            print(name)
        return 0
    if "--run" in argv:
        return _run(argv)
    print("usage: python -m evals.quality.runner [--selfcheck | --run | --list]")
    print("  --selfcheck               validate golden suites + metric math (no deps)")
    print("  --run [--suite NAME]      run the retrieval-backed quality eval")
    print("  --run --baseline FILE     compare against a saved suite JSON")
    print("  --run --json              emit JSON instead of markdown")
    print("  --list                    list available suites")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
