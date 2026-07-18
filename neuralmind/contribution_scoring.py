"""
E1 — Contribution-quality scoring for team memory bundles.

Scores each contributor's edges by:
- Reinforcement frequency (often-used edges are higher quality)
- Recency (recently-activated edges are more relevant)
- Conflict rate (edges that conflict with others are lower quality)

High-quality edges promote to `shared` namespace.
Low-quality edges stay in `personal`.

Requires C1 fitness (done) + A2 entity resolution (done).
Local-first. Stdlib-only. Fail-open.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any

# Quality thresholds for promotion
QUALITY_THRESHOLD_HIGH = 0.7  # edges above this promote to shared
QUALITY_THRESHOLD_LOW = 0.3  # edges below this are flagged for decay

# Scoring weights
WEIGHT_REINFORCEMENT = 0.4
WEIGHT_RECENCY = 0.35
WEIGHT_CONFLICT_PENALTY = 0.25


@dataclass
class EdgeQuality:
    """Quality score for a single contributor edge."""

    source: str
    target: str
    namespace: str
    score: float  # 0.0 to 1.0
    reinforcement_score: float
    recency_score: float
    conflict_rate: float
    activation_count: int
    age_days: float
    should_promote: bool
    should_decay: bool

    def to_dict(self) -> dict:
        return {
            "source": self.source,
            "target": self.target,
            "namespace": self.namespace,
            "score": round(self.score, 4),
            "reinforcement_score": round(self.reinforcement_score, 4),
            "recency_score": round(self.recency_score, 4),
            "conflict_rate": round(self.conflict_rate, 4),
            "activation_count": self.activation_count,
            "age_days": round(self.age_days, 1),
            "should_promote": self.should_promote,
            "should_decay": self.should_decay,
        }


class ContributionQualityScorer:
    """
    Scores edges from team-memory bundles by reinforcement, recency,
    and conflict rate. Outputs promote/decay decisions for E2 (merge
    semantics) and E3 (peer review gate) to consume.

    Fail-open: scoring errors return neutral 0.5 scores rather than
    raising, so a partial failure doesn't block team memory import.
    """

    def __init__(
        self,
        *,
        quality_high: float = QUALITY_THRESHOLD_HIGH,
        quality_low: float = QUALITY_THRESHOLD_LOW,
    ):
        self.quality_high = quality_high
        self.quality_low = quality_low

    def score_edge(
        self,
        source: str,
        target: str,
        namespace: str,
        activation_count: int,
        created_at: float,
        last_activated: float,
        conflict_count: int = 0,
        total_comparisons: int = 1,
    ) -> EdgeQuality:
        """Score a single edge on the three axes."""
        now = time.time()
        age_days = max(0.0, (now - created_at) / 86400.0)
        days_since_last = max(0.0, (now - last_activated) / 86400.0)

        # Reinforcement score: saturating function of activation_count
        # log1p(activations) / log1p(30) → ~1.0 at 30 activations
        import math

        reinforcement_score = min(1.0, math.log1p(activation_count) / math.log1p(30.0))

        # Recency score: exponential decay over 30 days
        recency_score = math.exp(-0.693 * days_since_last / 30.0)

        # Conflict rate: fraction of comparisons that conflicted
        conflict_rate = conflict_count / max(1, total_comparisons)

        # Combined score: weighted sum minus conflict penalty
        combined = (
            WEIGHT_REINFORCEMENT * reinforcement_score
            + WEIGHT_RECENCY * recency_score
            - WEIGHT_CONFLICT_PENALTY * conflict_rate
        )
        combined = max(0.0, min(1.0, combined))

        return EdgeQuality(
            source=source,
            target=target,
            namespace=namespace,
            score=combined,
            reinforcement_score=reinforcement_score,
            recency_score=recency_score,
            conflict_rate=conflict_rate,
            activation_count=activation_count,
            age_days=age_days,
            should_promote=combined >= self.quality_high,
            should_decay=combined < self.quality_low,
        )

    def score_bundle(
        self,
        bundle: dict[str, Any],
        *,
        source_namespace: str = "personal",
    ) -> list[EdgeQuality]:
        """Score all synapse edges in a team-memory bundle."""
        edges: list[EdgeQuality] = []
        for e in bundle.get("synapses", []):
            try:
                eq = self.score_edge(
                    source=e["source"],
                    target=e["target"],
                    namespace=source_namespace,
                    activation_count=int(e.get("activation_count", 1)),
                    created_at=float(e.get("created_at", time.time())),
                    last_activated=float(e.get("last_activated", time.time())),
                    conflict_count=int(e.get("conflicts", 0)),
                    total_comparisons=max(1, int(e.get("comparisons", 1))),
                )
                edges.append(eq)
            except (KeyError, TypeError, ValueError):
                # Skip malformed edges — fail-open
                continue
        return edges

    def classify_bundle(
        self,
        bundle: dict[str, Any],
    ) -> tuple[list[EdgeQuality], list[EdgeQuality], list[EdgeQuality]]:
        """
        Separate a bundle into promote/shared, neutral/personal, and
        decay/flagged edge lists.

        Returns: (promote_edges, neutral_edges, decay_edges)
        """
        scored = self.score_bundle(bundle)
        promote = [e for e in scored if e.should_promote]
        decay = [e for e in scored if e.should_decay]
        neutral = [e for e in scored if not e.should_promote and not e.should_decay]
        return promote, neutral, decay
