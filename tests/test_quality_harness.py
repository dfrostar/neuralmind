"""Regression gate + validation for the retrieval-quality eval suite (PRD 2).

The ``_selfcheck`` path is dependency-free (validates the golden suites and the
metric math) and runs everywhere. The retrieval-backed run needs the embedding
stack + a built fixture, so it's skipped cleanly when either is missing —
mirroring ``test_benchmark_regression``.
"""

from __future__ import annotations

import json
import math
import os
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from evals.quality import runner
from neuralmind.quality import hit_rate_at_k, ndcg_at_k

REPO_ROOT = Path(__file__).resolve().parents[1]
PY_FIXTURE_GRAPH = (
    REPO_ROOT / "tests" / "fixtures" / "sample_project" / "graphify-out" / "graph.json"
)


def test_selfcheck_passes():
    """Golden suites parse, cover 3 repos / >=25 queries, and metrics are sane."""
    assert runner._selfcheck() == 0


def test_suite_registry_has_ten_polyglot_suites():
    assert set(runner.all_suites()) == {
        "python",
        "typescript",
        "go",
        "rust",
        "java",
        "c",
        "cpp",
        "csharp",
        "ruby",
        "php",
    }
    assert runner.total_query_count() >= 50


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


def _hermetic_fixture(suite_name: str, tmp_path) -> str:
    """Copy a suite's committed fixture into tmp so the build never mutates the
    repo tree or cross-contaminates other tests in the same session."""
    import shutil

    src = runner.load_suite(suite_name).fixture_dir
    dst = tmp_path / src.name
    shutil.copytree(src, dst)
    return str(dst)


@pytest.mark.skipif(
    not _QUALITY_EVAL_ENABLED,
    reason="set NEURALMIND_QUALITY_EVAL=1 (needs real embeddings); runs in the self-benchmark workflow",
)
@pytest.mark.parametrize("suite_name", ["python", "typescript", "go"])
def test_suite_meets_quality_floor(suite_name, tmp_path):
    """End-to-end: real retrieval over each golden suite clears the absolute gate."""
    from evals.quality import harness

    try:
        report = harness.run_suite(suite_name, fixture_dir=_hermetic_fixture(suite_name, tmp_path))
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
def test_no_severe_regression_vs_committed_baseline(suite_name, tmp_path):
    """Each suite's MRR / answerability must stay within tolerance of the
    committed measured baseline — catches quiet drift the absolute floor misses."""
    from evals.quality import harness

    base = _load_baseline()[suite_name]
    try:
        report = harness.run_suite(suite_name, fixture_dir=_hermetic_fixture(suite_name, tmp_path))
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
    """The committed baseline parses and covers known suites with sanity-checked
    metrics. The baseline may be a subset (older baselines cover fewer suites),
    so we assert each entry it *does* carry is sane rather than requiring full
    parity with ``runner.all_suites()``."""
    base = _load_baseline()
    for name, m in base.items():
        assert name in runner.all_suites(), f"baseline suite {name!r} not in runner registry"
        assert 0.0 <= m["mrr"] <= 1.0, name
        assert 0.0 <= m["answerability"] <= 1.0, name
        assert "5" in m["mean_recall"], name


# --------------------------------------------------------------------------- #
# D2 — nDCG@k / hit-rate@k metric tests                                       #
# --------------------------------------------------------------------------- #


def test_ndcg_perfect():
    """All relevant items in the top-k → nDCG = 1.0."""
    ranked = ["a", "b", "c", "d", "e"]
    relevant = {"a", "b", "c"}
    assert ndcg_at_k(ranked, relevant, 5) == pytest.approx(1.0)


def test_ndcg_miss():
    """No relevant items in top-k → nDCG = 0.0."""
    ranked = ["x", "y", "z"]
    relevant = {"a", "b"}
    assert ndcg_at_k(ranked, relevant, 3) == 0.0


def test_ndcg_ordering():
    """Relevant items ranked earlier score higher than later."""
    ranked_good = ["a", "b", "c", "x", "y"]
    ranked_bad = ["x", "y", "a", "b", "c"]
    relevant = {"a", "b", "c"}
    assert ndcg_at_k(ranked_good, relevant, 5) > ndcg_at_k(ranked_bad, relevant, 5)


def test_ndcg_discount():
    """A single relevant item at rank 1 scores higher than at rank 5."""
    ranked_top = ["a", "x", "x", "x", "x"]
    ranked_deep = ["x", "x", "x", "x", "a"]
    relevant = {"a"}
    assert ndcg_at_k(ranked_top, relevant, 5) > ndcg_at_k(ranked_deep, relevant, 5)
    # Rank 1 → 1/log2(2) = 1.0; rank 5 → 1/log2(6) ≈ 0.38685
    assert ndcg_at_k(ranked_top, relevant, 5) == pytest.approx(1.0)
    assert ndcg_at_k(ranked_deep, relevant, 5) == pytest.approx(1.0 / math.log2(6))


def test_hit_rate_hit():
    """At least one relevant in top-k → 1.0."""
    ranked = ["x", "a", "y"]
    relevant = {"a"}
    assert hit_rate_at_k(ranked, relevant, 2) == 1.0


def test_hit_rate_miss():
    """No relevant in top-k → 0.0."""
    ranked = ["x", "y", "z"]
    relevant = {"a"}
    assert hit_rate_at_k(ranked, relevant, 3) == 0.0


def test_hit_rate_boundary():
    """Relevant item exactly at position k → 1.0; just past k → 0.0."""
    ranked = ["x", "x", "x", "a"]
    relevant = {"a"}
    assert hit_rate_at_k(ranked, relevant, 4) == 1.0
    assert hit_rate_at_k(ranked, relevant, 3) == 0.0


def test_aggregate_rolls_up_ndcg_and_hit_rate():
    """aggregate() computes mean_ndcg and mean_hit_rate alongside existing metrics."""
    from neuralmind import quality

    q1 = quality.evaluate_query("q1", ["a", "b"], ["a", "b"], ks=(1, 3, 5))
    q2 = quality.evaluate_query("q2", ["x", "y"], ["a", "b"], ks=(1, 3, 5))
    agg = quality.aggregate("test", [q1, q2], ks=(1, 3, 5))
    assert "mean_ndcg" in agg.to_dict()
    assert "mean_hit_rate" in agg.to_dict()
    # q1 perfect → ndcg@5=1.0, hit_rate@5=1.0; q2 miss → ndcg@5=0.0, hit_rate@5=0.0
    assert agg.mean_ndcg[5] == pytest.approx(0.5)
    assert agg.mean_hit_rate[5] == pytest.approx(0.5)


def test_thresholds_detect_bad_ndcg():
    """QualityThresholds.check() flags a suite with nDCG below floor."""
    from neuralmind import quality

    thresholds = quality.QualityThresholds(min_ndcg_at_k=0.5, ndcg_k=5)
    # Build a suite that passes MRR/answerability but fails nDCG
    q = quality.evaluate_query("q1", ["x", "y", "z"], ["a"], ks=(5,), answer_k=5)
    suite = quality.aggregate("test", [q], ks=(5,))
    failures = thresholds.check(suite)
    assert any("ndcg@5" in f for f in failures)


def test_thresholds_detect_bad_hit_rate():
    """QualityThresholds.check() flags a suite with hit-rate below floor."""
    from neuralmind import quality

    thresholds = quality.QualityThresholds(min_hit_rate_at_k=0.8, hit_rate_k=5)
    q = quality.evaluate_query("q1", ["x", "y", "z"], ["a"], ks=(5,), answer_k=5)
    suite = quality.aggregate("test", [q], ks=(5,))
    failures = thresholds.check(suite)
    assert any("hit_rate@5" in f for f in failures)


# --------------------------------------------------------------------------- #
# D1 — RAGAS-axis offline judge tests                                         #
# --------------------------------------------------------------------------- #


def test_ragas_facts_only():
    """score() with no embed_fn → cosine cols None, faithfulness populated."""
    from neuralmind.ragas import score

    result = score(
        query="How does auth work?",
        retrieved=["auth/handlers.py"],
        answer="The user is looked up by email and the password hash is verified. A JWT access token and refresh token pair is issued on success.",
        gold_facts=[
            "the user is looked up by email",
            "the password hash is verified",
            "a JWT access token and refresh token pair is issued on success",
        ],
    )
    assert result.context_precision is None
    assert result.context_recall is None
    assert result.answer_relevance is None
    assert 0.0 <= result.faithfulness <= 1.0
    # All facts present, no contradictions → faithfulness should be high
    assert result.faithfulness == pytest.approx(1.0)


def test_ragas_with_injected_fake_embeddings():
    """Deterministic fake embed_fn → pre-computed cosine columns."""
    from neuralmind.ragas import score

    # Fake embedder: hash-based deterministic 4-dim vectors
    def fake_embed(text: str) -> list[float]:
        h = hash(text) & 0xFFFF
        return [float((h >> (i * 4)) & 0xF) + 1.0 for i in range(4)]

    result = score(
        query="How does auth work?",
        retrieved=["auth/handlers.py", "users/crud.py"],
        answer="The user is looked up by email and the password hash is verified.",
        gold_facts=["the user is looked up by email", "the password hash is verified"],
        embed_fn=fake_embed,
    )
    assert result.context_precision is not None
    assert result.context_recall is not None
    assert result.answer_relevance is not None
    # Just verify it's a valid float in [-1, 1]
    assert -1.0 <= result.answer_relevance <= 1.0
    assert 0.0 <= result.context_precision <= 1.0
    assert 0.0 <= result.context_recall <= 1.0


def test_ragas_contradiction_detection():
    """Gold says sqlite, answer says postgresql → contradiction > 0."""
    from neuralmind.ragas import score

    result = score(
        query="What database does this project use?",
        retrieved=["db/connection.py"],
        answer="The project uses PostgreSQL as its database backend.",
        gold_facts=["the fixture uses SQLite"],
    )
    # Contradiction detected (sqlite vs postgresql are mutually exclusive)
    assert result.faithfulness < 1.0


def test_ragas_fact_boundaries():
    """Short needles (< 2 chars) are rejected from fact_recall denominator."""
    from neuralmind.ragas import fact_recall

    # Only short facts → denominator 0 → 0.0
    assert fact_recall("some answer", ["a", "b", ""]) == 0.0
    # Mix of short and valid → only valid counted
    result = fact_recall("the user is looked up by email", ["a", "the user is looked up by email"])
    assert result == pytest.approx(1.0)


def test_ragas_faithfulness_bounds():
    """Perfect facts → 1.0; totally wrong → low."""
    from neuralmind.ragas import score

    # Perfect: all facts present, no contradictions
    perfect = score(
        query="How does auth work?",
        retrieved=["auth/handlers.py"],
        answer="The user is looked up by email and the password hash is verified. A JWT access token and refresh token pair is issued on success.",
        gold_facts=[
            "the user is looked up by email",
            "the password hash is verified",
            "a JWT access token and refresh token pair is issued on success",
        ],
    )
    assert perfect.faithfulness == pytest.approx(1.0)

    # Totally wrong: none of the facts present
    wrong = score(
        query="How does auth work?",
        retrieved=["auth/handlers.py"],
        answer="The billing flow uses the Stripe API to charge customers.",
        gold_facts=[
            "the user is looked up by email",
            "the password hash is verified",
        ],
    )
    assert wrong.faithfulness < 0.5
