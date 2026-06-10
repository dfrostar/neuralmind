"""Regression gate + validation for the retrieval-quality eval suite (PRD 2).

The ``_selfcheck`` path is dependency-free (validates the golden suites and the
metric math) and runs everywhere. The retrieval-backed run needs the embedding
stack + a built fixture, so it's skipped cleanly when either is missing —
mirroring ``test_benchmark_regression``.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

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


def test_cmd_benchmark_routes_to_quality_only_on_literal_true(monkeypatch):
    """`benchmark --quality` enters quality mode; a bare MagicMock args must not.

    Regression guard: argparse `store_true` yields a real ``True``, but the
    benchmark unit tests pass a bare ``MagicMock()`` whose ``.quality`` is a
    truthy attribute — that must fall through to the normal token-reduction
    path, not the (file-reading) quality path.
    """
    from neuralmind import cli

    calls: list[str] = []
    monkeypatch.setattr(cli, "_run_quality_eval", lambda args: calls.append("quality"))

    # Real flag set -> routes to quality.
    cli.cmd_benchmark(SimpleNamespace(quality=True))
    assert calls == ["quality"]

    # Bare MagicMock -> must NOT route to quality; stub the normal path.
    calls.clear()
    monkeypatch.setattr(cli, "create_mind", lambda *a, **k: _StubMind())
    cli.cmd_benchmark(MagicMock(json=True, contribute=False))
    assert calls == []  # quality path never taken


class _StubMind:
    def benchmark(self):
        return {
            "project": "stub",
            "wakeup_tokens": 1,
            "avg_query_tokens": 1,
            "avg_reduction_ratio": 1.0,
            "summary": "ok",
        }


# The retrieval-backed run needs real embeddings (a model download), which the
# standard unit-test job firewalls off. It runs in the self-benchmark workflow,
# which sets NEURALMIND_QUALITY_EVAL=1 after building the fixtures. Gate on that
# env var so this neither hangs on a blocked download nor skips where it should
# run. A local dev can opt in with `NEURALMIND_QUALITY_EVAL=1 pytest ...`.
_QUALITY_EVAL_ENABLED = bool(os.environ.get("NEURALMIND_QUALITY_EVAL"))
_BASELINE_PATH = REPO_ROOT / "evals" / "quality" / "baseline.json"


@pytest.mark.skipif(
    not _QUALITY_EVAL_ENABLED,
    reason="set NEURALMIND_QUALITY_EVAL=1 (needs real embeddings); runs in the self-benchmark workflow",
)
@pytest.mark.parametrize("suite_name", ["python", "typescript", "go"])
def test_suite_meets_quality_floor(suite_name):
    """End-to-end: real retrieval over each golden suite clears the absolute gate."""
    from evals.quality import harness

    try:
        report = harness.run_suite(suite_name)
    except RuntimeError as exc:
        pytest.skip(f"retrieval stack unavailable for {suite_name}: {exc}")

    assert report.suite.n_queries >= 1
    assert report.passed, f"{suite_name} suite regressed below floor: {report.failures}"


def _load_baseline():
    return json.loads(_BASELINE_PATH.read_text(encoding="utf-8"))["suites"]


# Tolerance band below the committed baseline before we call it a regression —
# wide enough to absorb embedding-version / ordering noise, tight enough to
# catch a real ranking drop.
_REGRESSION_TOLERANCE = 0.15


@pytest.mark.skipif(
    not _QUALITY_EVAL_ENABLED,
    reason="set NEURALMIND_QUALITY_EVAL=1 (needs real embeddings); runs in the self-benchmark workflow",
)
@pytest.mark.parametrize("suite_name", ["python", "typescript", "go"])
def test_no_severe_regression_vs_committed_baseline(suite_name):
    """Each suite's MRR / answerability must stay within tolerance of the
    committed measured baseline — catches quiet drift the absolute floor misses."""
    from evals.quality import harness

    base = _load_baseline()[suite_name]
    try:
        report = harness.run_suite(suite_name)
    except RuntimeError as exc:
        pytest.skip(f"retrieval stack unavailable for {suite_name}: {exc}")

    s = report.suite
    assert s.mrr >= base["mrr"] - _REGRESSION_TOLERANCE, (
        f"{suite_name} MRR {s.mrr:.3f} regressed > {_REGRESSION_TOLERANCE} below "
        f"baseline {base['mrr']:.3f}"
    )
    assert s.answerability >= base["answerability"] - _REGRESSION_TOLERANCE, (
        f"{suite_name} answerability {s.answerability:.3f} regressed > "
        f"{_REGRESSION_TOLERANCE} below baseline {base['answerability']:.3f}"
    )


def test_committed_baseline_is_wellformed():
    """The committed baseline parses and covers all suites with sane metrics —
    a deps-free guard that runs everywhere, so a corrupted baseline is caught
    even when the retrieval-backed run is skipped."""
    base = _load_baseline()
    assert set(base) == set(runner.all_suites())
    for name, m in base.items():
        assert 0.0 <= m["mrr"] <= 1.0, name
        assert 0.0 <= m["answerability"] <= 1.0, name
        assert "5" in m["mean_recall"], name
