"""
E2 — Quality-weighted merge semantics for team memory.

When two contributors' edges conflict, merge with quality-weighted
resolution instead of last-write-wins. Higher-quality edges dominate.
Decay-on-conflict (reserved): losing edges would degrade faster, not be
deleted (team moves on, doesn't fork). Currently no caller passes losers
to merge_to_store(), so this path is unused. When both edges are too weak
to confidently resolve, decompose to a contest record (escalate to E3
peer review).

Requires E1 (scoring) + A2 (entity resolution, done).
Local-first. Stdlib-only. Fail-open.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any

from .contribution_scoring import ContributionQualityScorer, EdgeQuality
from .synapses import SHARED_NAMESPACE

# When both edges score below this threshold on a tie, the conflict
# is escalated rather than forced: emit a contest_record and mark
# unresolved (E3 peer review picks it up).
MERGE_TIE_THRESHOLD = 0.3


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
    winner: str = ""  # "a", "b", or "contest"
    merged_weight: float = 0.0
    contest: bool = False  # True when escalated to peer review

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
            "contest": self.contest,
        }


def _edge_quality_to_synapse_row(
    edge: EdgeQuality,
    weight_override: float | None = None,
) -> tuple[str, str, float, int]:
    """Convert an EdgeQuality to a (node_a, node_b, weight, count) row.

    Uses quality score as weight (capped by the synapse store at WEIGHT_CAP),
    and activation_count for lifetime activation tracking.
    """
    w = weight_override if weight_override is not None else edge.score
    return (edge.source, edge.target, float(w), edge.activation_count)


class QualityWeightedMerger:
    """
    Resolves conflicts between contributor edges using quality-weighted
    resolution. The edge with higher quality wins; ties fall back to
    the edge with higher activation count. Low-confidence ties decompose
    to contest records (escalate to E3).

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

        Returns MergeConflict with winner + merged weight. When both edges
        are too weak to confidently resolve (below MERGE_TIE_THRESHOLD and
        approximately tied), the conflict is marked as a contest.
        """
        conflict = MergeConflict(
            source=edge_a.source,
            target=edge_a.target,
            edge_a=edge_a,
            edge_b=edge_b,
            weight_a=edge_a.score,
            weight_b=edge_b.score,
        )

        score_diff = edge_a.score - edge_b.score
        abs_diff = abs(score_diff)

        # Both weak + close tie → escalate (don't force a low-confidence winner)
        if (
            edge_a.score < MERGE_TIE_THRESHOLD
            and edge_b.score < MERGE_TIE_THRESHOLD
            and abs_diff < 0.05
        ):
            conflict.winner = "contest"
            conflict.resolved = False
            conflict.contest = True
            conflict.merged_weight = 0.0
            return conflict

        # Quality-weighted resolution: the higher-quality edge wins
        if score_diff > 0:
            conflict.winner = "a"
            conflict.merged_weight = edge_a.score
            conflict.resolved = True
        elif score_diff < 0:
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

    def merge_to_store(
        self,
        merged: list[EdgeQuality],
        store: Any,
        namespace: str = SHARED_NAMESPACE,
        conflicts: list[MergeConflict] | None = None,
    ) -> dict[str, Any]:
        """Write merged edges into a SynapseStore in the target namespace.

        Each edge is written via ``import_edges`` (idempotent MAX-merge).
        Contest records (unresolved) are NOT written — they escalate to E3.

        Args:
            merged: quality-scored edges to merge.
            store: SynapseStore to merge into.
            namespace: target namespace (default: shared).
            conflicts: optional list of MergeConflict records; their losers
                are decayed before merge (write-loser-as-decayed).

        Returns: {"merged": int, "contest": int, "decayed": int}
        """
        now = time.time()
        rows: list[tuple[str, str, float, int]] = []
        contest_count = 0
        decayed_count = 0

        # Build lookup from conflicts for loser-decay
        conflict_by_key: dict[tuple[str, str], MergeConflict] = {}
        if conflicts:
            for c in conflicts:
                conflict_by_key[(c.source, c.target)] = c

        for edge in merged:
            key = (edge.source, edge.target)
            existing = conflict_by_key.get(key)
            if existing and existing.contest:
                contest_count += 1
                continue  # skip — escalate instead

            weight_override: float | None = None
            if existing and existing.resolved:
                loser = existing.edge_b if existing.winner == "a" else existing.edge_a
                if loser is edge:
                    # Apply decay-on-conflict to the loser
                    weight_override = loser.decay_weight(namespace)
                    decayed_count += 1

            rows.append(_edge_quality_to_synapse_row(edge, weight_override))

        count = store.import_edges(rows, namespace=namespace, now=now) if rows else 0

        return {
            "merged": count,
            "contest": contest_count,
            "decayed": decayed_count,
        }

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

        NOTE: transitions are silently dropped (v1 limitation). Only synapses
        are scored and merged. Callers needing transition merge must handle
        that separately.

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
                if conflict.contest:
                    pass  # Decompose: neither edge wins, escalate to E3
                else:
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
