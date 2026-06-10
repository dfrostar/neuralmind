"""Regression gate + validation for the retrieval-quality eval suite (PRD 2).

The ``_selfcheck`` path is dependency-free (validates the golden suites and the
metric math) and runs everywhere. The retrieval-backed run needs the embedding
stack + a built fixture, so it's skipped cleanly when either is missing —
mirroring ``test_benchmark_regression``.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from evals.quality import runner

REPO_ROOT = Path(__file__).resolve().parents[1]
PY_FIXTURE_GRAPH = (
    REPO_ROOT / "tests" / "fixtures" / "sample_project" / "graphify-out" / "graph.json"
)


def test_selfcheck_passes():
    """Golden suites parse, cover 3 repos / >=25 queries, and metrics are sane."""
    assert runner._selfcheck() == 0


def test_suite_registry_has_three_polyglot_suites():
    assert set(runner.all_suites()) == {"python", "typescript", "go"}
    assert runner.total_query_count() >= 25


def test_load_suite_rejects_unknown():
    with pytest.raises(ValueError):
        runner.load_suite("cobol")


def test_every_query_has_relevant_modules():
    for name in runner.all_suites():
        suite = runner.load_suite(name)
        for q in suite.queries:
            assert q.expected_modules, f"{name}/{q.id} has no expected_modules"


@pytest.mark.skipif(
    not PY_FIXTURE_GRAPH.exists(),
    reason="python fixture graph not built (CI builds it before pytest)",
)
def test_python_suite_meets_quality_floor():
    """End-to-end: retrieval over the built python fixture clears the gate."""
    try:
        from evals.quality import harness
    except Exception as exc:  # pragma: no cover
        pytest.skip(f"quality harness import failed: {exc}")

    try:
        report = harness.run_suite("python")
    except RuntimeError as exc:
        pytest.skip(f"retrieval stack unavailable: {exc}")

    assert report.suite.n_queries >= 1
    assert report.passed, f"python suite regressed: {report.failures}"
