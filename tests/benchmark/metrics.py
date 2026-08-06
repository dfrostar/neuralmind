"""Pure-Python retrieval metrics — stdlib-only.

Formulas (per-query, against a ranked ``actual`` list):
    recall@k      = |actual[:k] ∩ relevant| / |relevant|
    precision@k   = |actual[:k] ∩ relevant| / k
    mrr           = 1 / (index of first relevant item, 1-indexed); 0.0 if none
    ndcg@k        = DCG@k / IDCG@k
        DCG@k     = Σ (2**rel(i) - 1) / log2(i+1)  for i=1..k
        IDCG@k    = DCG@k of the ideal ordering (relevance-sorted)
    hit_rate      = 1.0 if actual ∩ relevant else 0.0

No external dependencies — these run anywhere pytest does.
"""

from __future__ import annotations

import math


def recall_at_k(actual: list[str], relevant: set[str], k: int) -> float:
    """Fraction of relevant items captured in the top-k results."""
    if not relevant or k <= 0:
        return 0.0
    hits = sum(1 for item in actual[:k] if item in relevant)
    return hits / len(relevant)


def precision_at_k(actual: list[str], relevant: set[str], k: int) -> float:
    """Fraction of the top-k results that are relevant."""
    if k <= 0:
        return 0.0
    hits = sum(1 for item in actual[:k] if item in relevant)
    return hits / k


def mrr(actual: list[str], relevant: set[str]) -> float:
    """Reciprocal rank of the first relevant item (0.0 if none)."""
    for i, item in enumerate(actual, start=1):
        if item in relevant:
            return 1.0 / i
    return 0.0


def ndcg_at_k(actual: list[str], relevance: dict[str, int], k: int) -> float:
    """Normalized discounted cumulative gain at k.

    ``relevance`` maps each item to its graded relevance (0=irrelevant,
    1=tangential, 2=relevant, 3=essential).  Items absent from the dict
    are treated as relevance 0.

    The ideal ordering is computed from **relevant items only** (v > 0),
    so grade-0 items do not inflate IDCG.
    """
    if k <= 0:
        return 0.0

    def dcg(items: list[str]) -> float:
        total = 0.0
        for i, item in enumerate(items, start=1):
            rel = relevance.get(item, 0)
            total += (2**rel - 1) / math.log2(i + 1)
        return total

    # Ideal: only relevant items (v > 0), sorted by relevance descending
    ideal = sorted(
        [k for k, v in relevance.items() if v > 0],
        key=lambda x: relevance[x],
        reverse=True,
    )
    ideal_score = dcg(ideal[:k])
    if ideal_score == 0.0:
        return 0.0
    return dcg(actual[:k]) / ideal_score


def hit_rate(actual: list[str], relevant: set[str]) -> float:
    """1.0 if any relevant item appears in actual, else 0.0."""
    return 1.0 if set(actual) & relevant else 0.0
