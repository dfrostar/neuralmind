"""Retrieval-quality metrics for the quality harness (PRD 2).

Token reduction proves NeuralMind is *cheap*; it does not prove the context it
selects is *relevant*. As ranking, clustering, and synapse recall evolve, a
change can look great on cost while quietly retrieving the wrong files. This
module is the relevance fitness function that catches that: standard
ranked-retrieval metrics computed against a golden set of expected modules.

Pure and stdlib-only — like the synapse and IR layers, the metrics and their
tests run without the embedding deps. The runner that feeds real retrieval
results in lives in ``evals/quality/`` (it ships with the source repo, not the
wheel), mirroring the faithfulness/onboarding evals.

Definitions (all over a *ranked* list of retrieved module paths vs a *set* of
relevant ones):

- **precision@k** — of the top-k results we actually returned, the fraction
  that are relevant. Denominator is ``min(k, len(ranked))`` so a suite that
  returns fewer than k items isn't penalized for the empty slots.
- **recall@k** — of the relevant modules, the fraction that appear in the
  top-k.
- **reciprocal rank** — ``1 / rank`` of the first relevant hit (0 if none);
  averaged across queries this is **MRR**.
- **answerable@k** — whether at least one relevant module is in the top-k. The
  query is, in principle, answerable from what was retrieved. Averaged, this is
  the **answerability rate**.
"""

from __future__ import annotations

import math
from collections.abc import Iterable
from dataclasses import dataclass, field

# Cutoffs reported by default. The primary cutoff (answerability + the headline
# precision/recall) is the largest; the smaller ones show ranking quality.
# 10 added for nDCG@10 / hit-rate@10 (PRD 2 D2).
DEFAULT_KS: tuple[int, ...] = (1, 3, 5, 10)


def dedup_preserve_order(items: Iterable[str]) -> list[str]:
    """Collapse a ranked list to first-occurrence order.

    Retrieval returns one hit per *symbol*, so several top hits can map to the
    same source file. For module-level metrics we rank each module by its best
    (earliest) hit and drop later duplicates.
    """
    seen: set[str] = set()
    out: list[str] = []
    for it in items:
        if not it or it in seen:
            continue
        seen.add(it)
        out.append(it)
    return out


def precision_at_k(ranked: list[str], relevant: set[str], k: int) -> float:
    if k <= 0:
        return 0.0
    top = ranked[:k]
    denom = min(k, len(top)) or 1
    hits = sum(1 for m in top if m in relevant)
    return hits / denom


def recall_at_k(ranked: list[str], relevant: set[str], k: int) -> float:
    if not relevant:
        return 0.0
    top = set(ranked[:k])
    return len(top & relevant) / len(relevant)


def reciprocal_rank(ranked: list[str], relevant: set[str]) -> float:
    for i, m in enumerate(ranked, start=1):
        if m in relevant:
            return 1.0 / i
    return 0.0


def answerable_at_k(ranked: list[str], relevant: set[str], k: int) -> bool:
    return bool(set(ranked[:k]) & relevant)


def ndcg_at_k(ranked: list[str], relevant: set[str], k: int) -> float:
    """Discounted Cumulative Gain / IDCG at k (binary relevance).

    Each relevant hit at rank *r* (1-based) contributes ``1/log2(r+1)`` to
    the DCG. The ideal DCG is the same sum over the top ``min(k, |relevant|)``
    ranks. Returns 0.0 when ``relevant`` is empty or ``k <= 0`` (nothing to
    gain), so a suite with no relevant gold never inflates the score.
    """
    if k <= 0 or not relevant:
        return 0.0
    dcg = 0.0
    for i, m in enumerate(ranked[:k], start=1):
        if m in relevant:
            dcg += 1.0 / math.log2(i + 1)
    # Ideal DCG: pack the |relevant| hits into the earliest ranks.
    n_ideal = min(k, len(relevant))
    idcg = sum(1.0 / math.log2(r + 1) for r in range(1, n_ideal + 1))
    if idcg <= 0.0:
        return 0.0
    return dcg / idcg


def hit_rate_at_k(ranked: list[str], relevant: set[str], k: int) -> float:
    """1.0 if any relevant module appears in the top-k, else 0.0."""
    if k <= 0 or not relevant:
        return 0.0
    return 1.0 if any(m in relevant for m in ranked[:k]) else 0.0


@dataclass
class QueryQuality:
    """Per-query metrics. ``ranked`` is the dedup'd module ranking evaluated."""

    query_id: str
    ranked: list[str]
    relevant: list[str]
    precision: dict[int, float] = field(default_factory=dict)
    recall: dict[int, float] = field(default_factory=dict)
    ndcg: dict[int, float] = field(default_factory=dict)
    hit_rate: dict[int, float] = field(default_factory=dict)
    reciprocal_rank: float = 0.0
    answerable: bool = False

    def to_dict(self) -> dict:
        return {
            "query_id": self.query_id,
            "ranked": self.ranked,
            "relevant": self.relevant,
            "precision": {str(k): round(v, 4) for k, v in self.precision.items()},
            "recall": {str(k): round(v, 4) for k, v in self.recall.items()},
            "ndcg": {str(k): round(v, 4) for k, v in self.ndcg.items()},
            "hit_rate": {str(k): round(v, 4) for k, v in self.hit_rate.items()},
            "reciprocal_rank": round(self.reciprocal_rank, 4),
            "answerable": self.answerable,
        }


def evaluate_query(
    query_id: str,
    ranked: Iterable[str],
    relevant: Iterable[str],
    *,
    ks: tuple[int, ...] = DEFAULT_KS,
    answer_k: int | None = None,
) -> QueryQuality:
    """Score one query's ranked retrieval against its relevant set."""
    ranked_list = dedup_preserve_order(ranked)
    relevant_set = set(relevant)
    answer_k = answer_k or (max(ks) if ks else 5)
    return QueryQuality(
        query_id=query_id,
        ranked=ranked_list,
        relevant=sorted(relevant_set),
        precision={k: precision_at_k(ranked_list, relevant_set, k) for k in ks},
        recall={k: recall_at_k(ranked_list, relevant_set, k) for k in ks},
        ndcg={k: ndcg_at_k(ranked_list, relevant_set, k) for k in ks},
        hit_rate={k: hit_rate_at_k(ranked_list, relevant_set, k) for k in ks},
        reciprocal_rank=reciprocal_rank(ranked_list, relevant_set),
        answerable=answerable_at_k(ranked_list, relevant_set, answer_k),
    )


@dataclass
class SuiteQuality:
    """Aggregate metrics over a query suite."""

    suite: str
    n_queries: int
    ks: tuple[int, ...]
    mean_precision: dict[int, float]
    mean_recall: dict[int, float]
    mean_ndcg: dict[int, float]
    mean_hit_rate: dict[int, float]
    mrr: float
    answerability: float
    per_query: list[QueryQuality] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "suite": self.suite,
            "n_queries": self.n_queries,
            "ks": list(self.ks),
            "mean_precision": {str(k): round(v, 4) for k, v in self.mean_precision.items()},
            "mean_recall": {str(k): round(v, 4) for k, v in self.mean_recall.items()},
            "mean_ndcg": {str(k): round(v, 4) for k, v in self.mean_ndcg.items()},
            "mean_hit_rate": {str(k): round(v, 4) for k, v in self.mean_hit_rate.items()},
            "mrr": round(self.mrr, 4),
            "answerability": round(self.answerability, 4),
            "per_query": [q.to_dict() for q in self.per_query],
        }


def _mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def aggregate(
    suite: str,
    per_query: list[QueryQuality],
    *,
    ks: tuple[int, ...] = DEFAULT_KS,
) -> SuiteQuality:
    """Roll per-query metrics up into suite-level means / MRR / answerability."""
    return SuiteQuality(
        suite=suite,
        n_queries=len(per_query),
        ks=ks,
        mean_precision={k: _mean([q.precision.get(k, 0.0) for q in per_query]) for k in ks},
        mean_recall={k: _mean([q.recall.get(k, 0.0) for q in per_query]) for k in ks},
        mean_ndcg={k: _mean([q.ndcg.get(k, 0.0) for q in per_query]) for k in ks},
        mean_hit_rate={k: _mean([q.hit_rate.get(k, 0.0) for q in per_query]) for k in ks},
        mrr=_mean([q.reciprocal_rank for q in per_query]),
        answerability=_mean([1.0 if q.answerable else 0.0 for q in per_query]),
        per_query=per_query,
    )


# --------------------------------------------------------------------------- #
# Thresholds / regression gating
# --------------------------------------------------------------------------- #


@dataclass
class QualityThresholds:
    """Minimum acceptable suite metrics for the CI regression gate.

    Conservative floors — well below NeuralMind's real retrieval quality — so
    the gate catches genuine regressions (a ranking change that drops relevant
    files), not normal noise. Tunable per suite via the runner.
    """

    min_mrr: float = 0.5
    min_answerability: float = 0.7
    min_recall_at_k: float = 0.5
    recall_k: int = 5
    min_ndcg_at_k: float = 0.5
    ndcg_k: int = 5
    min_hit_rate_at_k: float = 0.8
    hit_rate_k: int = 5

    def check(self, suite: SuiteQuality) -> list[str]:
        """Return a list of human-readable failure messages (empty == pass)."""
        failures: list[str] = []
        if suite.mrr < self.min_mrr:
            failures.append(f"MRR {suite.mrr:.3f} < floor {self.min_mrr:.3f}")
        if suite.answerability < self.min_answerability:
            failures.append(
                f"answerability {suite.answerability:.3f} < floor {self.min_answerability:.3f}"
            )
        recall = suite.mean_recall.get(self.recall_k)
        if recall is not None and recall < self.min_recall_at_k:
            failures.append(
                f"recall@{self.recall_k} {recall:.3f} < floor {self.min_recall_at_k:.3f}"
            )
        ndcg = suite.mean_ndcg.get(self.ndcg_k)
        if ndcg is not None and ndcg < self.min_ndcg_at_k:
            failures.append(
                f"ndcg@{self.ndcg_k} {ndcg:.3f} < floor {self.min_ndcg_at_k:.3f}"
            )
        hit_rate = suite.mean_hit_rate.get(self.hit_rate_k)
        if hit_rate is not None and hit_rate < self.min_hit_rate_at_k:
            failures.append(
                f"hit_rate@{self.hit_rate_k} {hit_rate:.3f} < floor {self.min_hit_rate_at_k:.3f}"
            )
        return failures


@dataclass
class BaselineDelta:
    """A metric's movement vs a saved baseline (negative == regression)."""

    metric: str
    baseline: float
    current: float

    @property
    def delta(self) -> float:
        return self.current - self.baseline

    def to_dict(self) -> dict:
        return {
            "metric": self.metric,
            "baseline": round(self.baseline, 4),
            "current": round(self.current, 4),
            "delta": round(self.delta, 4),
        }


def compare_to_baseline(suite: SuiteQuality, baseline: dict) -> list[BaselineDelta]:
    """Diff a suite's headline metrics against a previously saved ``to_dict``.

    Compares MRR, answerability, mean recall, mean nDCG, and mean hit-rate.
    Missing baseline keys are skipped so an older baseline still produces a
    partial comparison.
    """
    deltas: list[BaselineDelta] = []
    if "mrr" in baseline:
        deltas.append(BaselineDelta("mrr", float(baseline["mrr"]), suite.mrr))
    if "answerability" in baseline:
        deltas.append(
            BaselineDelta("answerability", float(baseline["answerability"]), suite.answerability)
        )
    base_recall = baseline.get("mean_recall", {})
    for k in suite.ks:
        key = str(k)
        if key in base_recall:
            deltas.append(
                BaselineDelta(
                    f"recall@{k}",
                    float(base_recall[key]),
                    suite.mean_recall.get(k, 0.0),
                )
            )
    base_ndcg = baseline.get("mean_ndcg", {})
    for k in suite.ks:
        key = str(k)
        if key in base_ndcg:
            deltas.append(
                BaselineDelta(
                    f"ndcg@{k}",
                    float(base_ndcg[key]),
                    suite.mean_ndcg.get(k, 0.0),
                )
            )
    base_hit_rate = baseline.get("mean_hit_rate", {})
    for k in suite.ks:
        key = str(k)
        if key in base_hit_rate:
            deltas.append(
                BaselineDelta(
                    f"hit_rate@{k}",
                    float(base_hit_rate[key]),
                    suite.mean_hit_rate.get(k, 0.0),
                )
            )
    return deltas
