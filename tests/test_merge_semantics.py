"""Tests for E2 — quality-weighted merge semantics."""

import time

from neuralmind.contribution_scoring import ContributionQualityScorer, EdgeQuality
from neuralmind.merge_semantics import QualityWeightedMerger


class TestQualityWeightedMerger:
    def test_higher_quality_wins(self):
        scorer = ContributionQualityScorer()
        merger = QualityWeightedMerger(scorer)

        hot_edge = scorer.score_edge(
            source="a",
            target="b",
            namespace="shared",
            activation_count=50,
            created_at=time.time() - 86400,
            last_activated=time.time(),
            conflict_count=0,
            total_comparisons=10,
        )
        cold_edge = scorer.score_edge(
            source="a",
            target="b",
            namespace="personal",
            activation_count=1,
            created_at=time.time() - 86400 * 90,
            last_activated=time.time() - 86400 * 80,
            conflict_count=3,
            total_comparisons=5,
        )

        conflict = merger.resolve_conflict(hot_edge, cold_edge)
        assert conflict.winner == "a"
        assert conflict.resolved

    def test_tiebreaker_uses_activation_count(self):
        scorer = ContributionQualityScorer()
        merger = QualityWeightedMerger(scorer)

        # Two identical-quality edges with different activation counts
        edge_a = EdgeQuality(
            source="x",
            target="y",
            namespace="shared",
            score=0.5,
            reinforcement_score=0.5,
            recency_score=0.5,
            conflict_rate=0.0,
            activation_count=100,
            age_days=1.0,
            should_promote=False,
            should_decay=False,
        )
        edge_b = EdgeQuality(
            source="x",
            target="y",
            namespace="personal",
            score=0.5,
            reinforcement_score=0.5,
            recency_score=0.5,
            conflict_rate=0.0,
            activation_count=200,
            age_days=1.0,
            should_promote=False,
            should_decay=False,
        )

        conflict = merger.resolve_conflict(edge_a, edge_b)
        assert conflict.winner == "b"  # higher activation count wins ties
