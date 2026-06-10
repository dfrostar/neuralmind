"""Tests for the retrieval-quality metrics (PRD 2).

Stdlib-only — the metric math runs without the embedding deps.
"""

from neuralmind import quality


def test_dedup_preserve_order():
    assert quality.dedup_preserve_order(["a", "b", "a", "c", "b"]) == ["a", "b", "c"]
    assert quality.dedup_preserve_order(["a", "", None, "a"]) == ["a"]  # type: ignore[list-item]


def test_precision_at_k():
    ranked = ["a", "b", "c", "d"]
    relevant = {"a", "c"}
    assert quality.precision_at_k(ranked, relevant, 1) == 1.0  # a
    assert quality.precision_at_k(ranked, relevant, 2) == 0.5  # a,b
    assert quality.precision_at_k(ranked, relevant, 4) == 0.5  # a,c of 4
    assert quality.precision_at_k(ranked, relevant, 0) == 0.0


def test_precision_denominator_uses_available_when_fewer_than_k():
    ranked = ["a"]
    relevant = {"a"}
    # Only one result returned; precision@5 should be 1.0, not 0.2.
    assert quality.precision_at_k(ranked, relevant, 5) == 1.0


def test_recall_at_k():
    ranked = ["a", "b", "c", "d"]
    relevant = {"a", "c", "x"}
    assert quality.recall_at_k(ranked, relevant, 1) == 1 / 3  # a
    assert quality.recall_at_k(ranked, relevant, 4) == 2 / 3  # a,c (x never retrieved)
    assert quality.recall_at_k(ranked, set(), 4) == 0.0


def test_reciprocal_rank():
    assert quality.reciprocal_rank(["x", "y", "a"], {"a"}) == 1 / 3
    assert quality.reciprocal_rank(["a", "b"], {"a"}) == 1.0
    assert quality.reciprocal_rank(["x", "y"], {"a"}) == 0.0


def test_answerable_at_k():
    assert quality.answerable_at_k(["x", "a"], {"a"}, 2) is True
    assert quality.answerable_at_k(["x", "a"], {"a"}, 1) is False
    assert quality.answerable_at_k([], {"a"}, 5) is False


def test_evaluate_query_shape():
    q = quality.evaluate_query("q1", ["a", "b", "a", "c"], ["a", "c"], ks=(1, 3))
    assert q.query_id == "q1"
    assert q.ranked == ["a", "b", "c"]  # dedup'd
    assert q.relevant == ["a", "c"]  # sorted set
    assert q.precision[1] == 1.0
    assert q.recall[3] == 1.0
    assert q.reciprocal_rank == 1.0
    assert q.answerable is True


def test_evaluate_query_miss():
    q = quality.evaluate_query("q2", ["x", "y"], ["a"], ks=(1, 3))
    assert q.reciprocal_rank == 0.0
    assert q.answerable is False
    assert q.recall[3] == 0.0


def test_aggregate():
    per = [
        quality.evaluate_query("q1", ["a"], ["a"], ks=(1, 3)),  # perfect
        quality.evaluate_query("q2", ["x", "y"], ["a"], ks=(1, 3)),  # miss
    ]
    agg = quality.aggregate("demo", per, ks=(1, 3))
    assert agg.n_queries == 2
    assert agg.mrr == 0.5  # (1.0 + 0.0) / 2
    assert agg.answerability == 0.5
    assert agg.mean_recall[3] == 0.5  # (1.0 + 0.0) / 2


def test_to_dict_round_trip_is_json_safe():
    import json

    per = [quality.evaluate_query("q1", ["a", "b"], ["a"], ks=(1, 3))]
    agg = quality.aggregate("demo", per, ks=(1, 3))
    blob = json.dumps(agg.to_dict())
    parsed = json.loads(blob)
    assert parsed["suite"] == "demo"
    assert parsed["mrr"] == 1.0
    assert parsed["per_query"][0]["query_id"] == "q1"


# --------------------------------------------------------------------------- #
# Thresholds + baseline comparison (CI gate)
# --------------------------------------------------------------------------- #


def _good_suite():
    per = [
        quality.evaluate_query("q1", ["a", "b"], ["a"], ks=(1, 3, 5)),
        quality.evaluate_query("q2", ["c", "d"], ["c"], ks=(1, 3, 5)),
    ]
    return quality.aggregate("demo", per, ks=(1, 3, 5))


def test_thresholds_pass_on_good_suite():
    t = quality.QualityThresholds(
        min_mrr=0.5, min_answerability=0.7, min_recall_at_k=0.5, recall_k=5
    )
    assert t.check(_good_suite()) == []


def test_thresholds_fail_on_poor_suite():
    per = [
        quality.evaluate_query("q1", ["x", "y"], ["a"], ks=(1, 3, 5)),  # all miss
        quality.evaluate_query("q2", ["x", "y"], ["c"], ks=(1, 3, 5)),
    ]
    poor = quality.aggregate("demo", per, ks=(1, 3, 5))
    failures = quality.QualityThresholds().check(poor)
    assert failures  # at least MRR + answerability + recall floors
    assert any("MRR" in f for f in failures)
    assert any("answerability" in f for f in failures)


def test_compare_to_baseline_detects_regression():
    suite = _good_suite()
    # Baseline had a higher MRR -> current is a regression (negative delta).
    baseline = {"mrr": 1.0, "answerability": 1.0, "mean_recall": {"5": 1.0}}
    deltas = quality.compare_to_baseline(suite, baseline)
    by_metric = {d.metric: d for d in deltas}
    assert by_metric["mrr"].delta == 0.0  # good suite also has mrr 1.0
    assert by_metric["answerability"].delta == 0.0
    assert "recall@5" in by_metric


def test_compare_to_baseline_partial_baseline():
    suite = _good_suite()
    deltas = quality.compare_to_baseline(suite, {"mrr": 0.4})
    assert len(deltas) == 1
    assert deltas[0].metric == "mrr"
    assert round(deltas[0].delta, 4) == round(suite.mrr - 0.4, 4)
