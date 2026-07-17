"""
E3 — Peer review gate for team-memory contributions.

Team-memory contributions above a quality threshold auto-promote to
`shared`. Below the threshold, edges are flagged for human review
before entering the shared namespace.

Requires E1 (scoring) + E2 (merge semantics).

Local-first. Stdlib-only. Fail-open.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .contribution_scoring import ContributionQualityScorer, EdgeQuality

# Threshold: edges at or above this score auto-promote to shared
AUTO_PROMOTE_THRESHOLD = 0.75

# Edges below this score are rejected outright
REJECT_THRESHOLD = 0.15


@dataclass
class ReviewDecision:
    """Decision for a single team-memory edge."""
    edge: EdgeQuality
    action: str  # "auto_promote" | "review_required" | "reject"
    reason: str = ""
    reviewer_hint: str = ""

    def to_dict(self) -> dict:
        return {
            "source": self.edge.source,
            "target": self.edge.target,
            "score": round(self.edge.score, 4),
            "action": self.action,
            "reason": self.reason,
            "reviewer_hint": self.reviewer_hint,
        }


class PeerReviewGate:
    """
    Decides which team-memory contributions auto-promote vs require
    human review before entering `shared`. Above-threshold edges pass
    through directly; below-threshold but above-reject edges are flagged
    for human review; very low scores are rejected.
    """

    def __init__(
        self,
        scorer: ContributionQualityScorer | None = None,
        auto_promote: float = AUTO_PROMOTE_THRESHOLD,
        reject: float = REJECT_THRESHOLD,
    ):
        self.scorer = scorer or ContributionQualityScorer()
        self.auto_promote = auto_promote
        self.reject = reject

    def decide(self, edge: EdgeQuality) -> ReviewDecision:
        """
        Classify one edge into auto-promote, review-required, or reject.
        
        - score >= auto_promote threshold → auto-promote
        - score < reject threshold → reject
        - otherwise → flag for review
        """
        if edge.score >= self.auto_promote:
            return ReviewDecision(
                edge=edge,
                action="auto_promote",
                reason=f"score {edge.score:.3f} >= auto_promote {self.auto_promote}",
            )
        elif edge.score < self.reject:
            return ReviewDecision(
                edge=edge,
                action="reject",
                reason=f"score {edge.score:.3f} < reject {self.reject}",
                reviewer_hint="Low reinforcement + stale + high conflict — likely noise.",
            )
        else:
            hint_parts = []
            if edge.reinforcement_score < 0.3:
                hint_parts.append("low reinforcement")
            if edge.recency_score < 0.3:
                hint_parts.append("stale")
            if edge.conflict_rate > 0.5:
                hint_parts.append("high conflict")
            hint = ", ".join(hint_parts) if hint_parts else "marginal score"

            return ReviewDecision(
                edge=edge,
                action="review_required",
                reason=f"score {edge.score:.3f} in review band [{self.reject}, {self.auto_promote})",
                reviewer_hint=hint,
            )

    def gate_bundle(
        self,
        bundle: dict[str, Any],
    ) -> tuple[list[ReviewDecision], list[ReviewDecision], list[ReviewDecision]]:
        """
        Apply the peer-review gate to all edges in a bundle.
        
        Returns: (auto_promoted, review_required, rejected)
        """
        scored = self.scorer.score_bundle(bundle)
        auto_promoted: list[ReviewDecision] = []
        review_required: list[ReviewDecision] = []
        rejected: list[ReviewDecision] = []

        for edge in scored:
            decision = self.decide(edge)
            if decision.action == "auto_promote":
                auto_promoted.append(decision)
            elif decision.action == "review_required":
                review_required.append(decision)
            else:
                rejected.append(decision)

        return auto_promoted, review_required, rejected
