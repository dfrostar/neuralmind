"""Tests for E2 — quality-weighted merge semantics."""

import time

from neuralmind.contribution_scoring import ContributionQualityScorer, EdgeQuality
from neuralmind.merge_semantics import MERGE_TIE_THRESHOLD, QualityWeightedMerger
from neuralmind.synapses import SHARED_NAMESPACE, SynapseStore


class TestQualityWeightedMerger:
    def test_high_quality_wins_conflict(self):
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
        assert conflict.merged_weight == hot_edge.score

    def test_low_quality_decays(self):
        scorer = ContributionQualityScorer()
        merger = QualityWeightedMerger(scorer)

        hot_edge = scorer.score_edge(
            source="a",
            target="b",
            namespace="shared",
            activation_count=50,
            created_at=time.time() - 86400,
            last_activated=time.time(),
        )
        cold_edge = scorer.score_edge(
            source="a",
            target="b",
            namespace="personal",
            activation_count=1,
            created_at=time.time() - 86400 * 40,
            last_activated=time.time() - 86400 * 30,
            conflict_count=1,
            total_comparisons=5,
        )
        assert cold_edge.score > 0.0, "test precondition: loser must have positive score"

        # Loser's decay_weight should be less than original score
        decayed = cold_edge.decay_weight("shared")
        assert decayed < cold_edge.score
        assert decayed >= 0.01  # floor

        # Chronic loser (high conflict) decays faster than clean loser
        clean_edge = scorer.score_edge(
            source="a",
            target="b",
            namespace="personal",
            activation_count=1,
            created_at=time.time() - 86400 * 10,
            last_activated=time.time() - 86400 * 5,
        )
        assert decayed <= clean_edge.decay_weight("shared")

    def test_tie_breaker_by_activation(self):
        scorer = ContributionQualityScorer()
        merger = QualityWeightedMerger(scorer)

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

    def test_decay_on_conflict_reduces_weight_over_time(self):
        scorer = ContributionQualityScorer()
        merger = QualityWeightedMerger(scorer)

        edge_a = scorer.score_edge(
            source="a",
            target="b",
            namespace="shared",
            activation_count=50,
            created_at=time.time() - 86400,
            last_activated=time.time(),
        )
        edge_b = scorer.score_edge(
            source="a",
            target="b",
            namespace="personal",
            activation_count=1,
            created_at=time.time() - 86400 * 40,
            last_activated=time.time() - 86400 * 30,
            conflict_count=1,
            total_comparisons=5,
        )
        assert edge_b.score > 0.0, "test precondition: loser must have positive score"

        conflict = merger.resolve_conflict(edge_a, edge_b)
        loser = conflict.edge_b if conflict.winner == "a" else conflict.edge_a

        # Apply decay multiple times (simulates repeated losing)
        weight = loser.score
        for _ in range(5):
            weight = EdgeQuality(
                source=loser.source,
                target=loser.target,
                namespace=loser.namespace,
                score=weight,
                reinforcement_score=loser.reinforcement_score,
                recency_score=loser.recency_score,
                conflict_rate=loser.conflict_rate,
                activation_count=loser.activation_count,
                age_days=loser.age_days,
                should_promote=loser.should_promote,
                should_decay=loser.should_decay,
            ).decay_weight("shared")

        assert weight < loser.score

    def test_fail_open_on_scoring_error(self):
        """Scorer raises on missing source/target — merger should skip, not crash."""
        scorer = ContributionQualityScorer()
        merger = QualityWeightedMerger(scorer)

        # Malformed edge: score_bundle skips it (fail-open)
        bundle = {"synapses": [{"weight": 1.0, "activation_count": 1}]}
        scored = scorer.score_bundle(bundle)
        assert scored == []  # malformed edge skipped

        # Merger handles empty scored list gracefully
        bundle_a = {
            "synapses": [
                {
                    "source": "a",
                    "target": "b",
                    "weight": 1.0,
                    "activation_count": 1,
                    "created_at": time.time(),
                    "last_activated": time.time(),
                }
            ]
        }
        bundle_b = {"synapses": [{"weight": 2.0, "activation_count": 5}]}  # malformed

        merged, conflicts = merger.merge_bundles(bundle_a, bundle_b)
        assert len(merged) == 1  # only valid edge from A
        assert len(conflicts) == 0

    def test_contest_escalation_both_weak(self):
        """When both edges are weak + close tie, conflict escalates to contest."""
        scorer = ContributionQualityScorer()
        merger = QualityWeightedMerger(scorer)

        # Two weak edges (below MERGE_TIE_THRESHOLD, close in score)
        edge_a = EdgeQuality(
            source="x",
            target="y",
            namespace="personal",
            score=MERGE_TIE_THRESHOLD - 0.05,
            reinforcement_score=0.1,
            recency_score=0.1,
            conflict_rate=0.2,
            activation_count=2,
            age_days=30.0,
            should_promote=False,
            should_decay=True,
        )
        edge_b = EdgeQuality(
            source="x",
            target="y",
            namespace="personal",
            score=MERGE_TIE_THRESHOLD - 0.06,
            reinforcement_score=0.1,
            recency_score=0.1,
            conflict_rate=0.2,
            activation_count=2,
            age_days=30.0,
            should_promote=False,
            should_decay=True,
        )

        conflict = merger.resolve_conflict(edge_a, edge_b)
        assert conflict.contest
        assert not conflict.resolved
        assert conflict.winner == "contest"

    def test_merge_to_store_excludes_contests(self):
        """merge_to_store skips contest records (escalates instead)."""
        scorer = ContributionQualityScorer()
        merger = QualityWeightedMerger(scorer)

        # Create a temp store for testing
        import tempfile
        from pathlib import Path

        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            store = SynapseStore(db_path, namespace=SHARED_NAMESPACE)

            edges = [
                scorer.score_edge(
                    source="a",
                    target="b",
                    namespace=SHARED_NAMESPACE,
                    activation_count=10,
                    created_at=time.time() - 86400,
                    last_activated=time.time(),
                ),
                scorer.score_edge(
                    source="c",
                    target="d",
                    namespace=SHARED_NAMESPACE,
                    activation_count=8,
                    created_at=time.time() - 86400,
                    last_activated=time.time(),
                ),
            ]

            # No conflicts
            result = merger.merge_to_store(edges, store)
            assert result["merged"] == 2
            assert result["contest"] == 0
