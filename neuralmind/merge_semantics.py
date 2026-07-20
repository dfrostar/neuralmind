"""
E2 — Quality-weighted merge semantics for team memory.

When two contributors' edges conflict, merge with quality-weighted
resolution instead of last-write-wins. Higher-quality edges dominate.

Requires E1 (scoring) + A2 (entity resolution, done).
Local-first. Stdlib-only. Fail-open.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .contribution_scoring import ContributionQualityScorer, EdgeQuality


@dataclass
class MergeConflict:
    """Two edges that disagree on the same (source, target) pair."""

    source: str
    target: str
    edge_a: EdgeQuality
    edge_b: EdgeQuality
    weight_a: float = 0.0
    weight_b: float = 0.0
    resolved: bool = False
    winner: str = ""  # "a" or "b"
    merged_weight: float = 0.0

    def to_dict(self) -> dict:
        return {
            "source": self.source,
            "target": self.target,
            "quality_a": round(self.edge_a.score, 4),
            "quality_b": round(self.edge_b.score, 4),
            "weight_a": round(self.weight_a, 4),
            "weight_b": round(self.weight_b, 4),
            "winner": self.winner,
            "resolved": self.resolved,
            "merged_weight": round(self.merged_weight, 4),
        }


class QualityWeightedMerger:
    """
    Resolves conflicts between contributor edges using quality-weighted
    resolution. The edge with higher quality wins; ties fall back to
    the edge with higher activation count.

    Fail-open: if scoring fails for either edge, the original edge stands
    rather than corrupting the namespace.
    """

    def __init__(self, scorer: ContributionQualityScorer | None = None):
        self.scorer = scorer or ContributionQualityScorer()

    def resolve_conflict(
        self,
        edge_a: EdgeQuality,
        edge_b: EdgeQuality,
    ) -> MergeConflict:
        """
        Resolve a conflict between two edges for the same (source, target).

        Returns MergeConflict with winner + merged weight.
        """
        conflict = MergeConflict(
            source=edge_a.source,
            target=edge_a.target,
            edge_a=edge_a,
            edge_b=edge_b,
            weight_a=edge_a.score,
            weight_b=edge_b.score,
        )

        # Quality-weighted resolution: the higher-quality edge wins
        if edge_a.score > edge_b.score:
            conflict.winner = "a"
            conflict.merged_weight = edge_a.score
            conflict.resolved = True
        elif edge_b.score > edge_a.score:
            conflict.winner = "b"
            conflict.merged_weight = edge_b.score
            conflict.resolved = True
        else:
            # Exact tie: use activation count as tiebreaker
            if edge_a.activation_count >= edge_b.activation_count:
                conflict.winner = "a"
                conflict.merged_weight = edge_a.score
            else:
                conflict.winner = "b"
                conflict.merged_weight = edge_b.score
            conflict.resolved = True

        return conflict

    def merge_bundles(
        self,
        bundle_a: dict[str, Any],
        bundle_b: dict[str, Any],
        target_namespace: str = "shared",
    ) -> tuple[list[EdgeQuality], list[MergeConflict]]:
        """
        Merge two team-memory bundles, resolving conflicts quality-weighted.

        Scores both bundles, then for overlapping (source, target) pairs,
        the higher-quality edge wins. Non-overlapping edges pass through
        with their score.

        Note: target_namespace is reserved for future use. Current
        implementation preserves each edge's original namespace.

        Returns: (merged_edges, conflicts_resolved)
        """
        scored_a = self.scorer.score_bundle(bundle_a)
        scored_b = self.scorer.score_bundle(bundle_b)

        # Index by (source, target) for overlap detection
        index_a: dict[tuple[str, str], EdgeQuality] = {(e.source, e.target): e for e in scored_a}
        index_b: dict[tuple[str, str], EdgeQuality] = {(e.source, e.target): e for e in scored_b}

        merged: list[EdgeQuality] = []
        conflicts: list[MergeConflict] = []

        # Process all edges from A
        for key, edge_a in index_a.items():
            if key in index_b:
                # Conflict — resolve
                conflict = self.resolve_conflict(edge_a, index_b[key])
                conflicts.append(conflict)
                # Winner becomes the merged edge
                winner_edge = edge_a if conflict.winner == "a" else index_b[key]
                merged.append(winner_edge)
            else:
                merged.append(edge_a)

        # Add non-overlapping edges from B
        for key, edge_b in index_b.items():
            if key not in index_a:
                merged.append(edge_b)

        return merged, conflicts
