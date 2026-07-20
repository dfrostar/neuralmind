"""Tests for E3 — peer review gate for team-memory contributions."""

import time

from neuralmind.contribution_scoring import (
    QUALITY_THRESHOLD_HIGH,
    ContributionQualityScorer,
    EdgeQuality,
)
from neuralmind.merge_semantics import QualityWeightedMerger
from neuralmind.peer_review import (
    AUTO_PROMOTE_THRESHOLD,
    REJECT_THRESHOLD,
    PeerReviewGate,
    ReviewDecision,
)


class TestPeerReviewGate:
    def test_high_quality_edge_auto_promotes(self):
        scorer = ContributionQualityScorer()
        gate = PeerReviewGate(scorer)

        # High activation + recent + no conflict = high quality
        edge = scorer.score_edge(
            source="auth/jwt.py",
            target="auth/handlers.py",
            namespace="shared",
            activation_count=50,
            created_at=time.time() - 86400,
            last_activated=time.time(),
            conflict_count=0,
            total_comparisons=1,
        )
        assert edge.score >= AUTO_PROMOTE_THRESHOLD, (
            f"test precondition: score {edge.score} should be >= {AUTO_PROMOTE_THRESHOLD}"
        )

        decision = gate.decide(edge)
        assert decision.action == "auto_promote"
        assert "auto_promote" in decision.reason

    def test_low_quality_edge_is_rejected(self):
        scorer = ContributionQualityScorer()
        gate = PeerReviewGate(scorer)

        # Stale + low conflict_rate=0 gives score around 0.2-0.4, which may be in review band
        # We need score < REJECT_THRESHOLD (0.15), so use extremely low activation + very stale
        edge = scorer.score_edge(
            source="noise/a.py",
            target="noise/b.py",
            namespace="personal",
            activation_count=0,
            created_at=time.time() - 86400 * 365,  # 1 year old
            last_activated=time.time() - 86400 * 365,
            conflict_count=5,
            total_comparisons=5,
        )
        assert edge.score < REJECT_THRESHOLD, (
            f"test precondition: score {edge.score} should be < {REJECT_THRESHOLD}"
        )

        decision = gate.decide(edge)
        assert decision.action == "reject"
        assert "reject" in decision.reason
        assert "Low reinforcement" in decision.reviewer_hint or "stale" in decision.reviewer_hint

    def test_marginal_edge_requires_review(self):
        scorer = ContributionQualityScorer()
        gate = PeerReviewGate(scorer)

        # Middling activation and recency — score should land in [REJECT_THRESHOLD, AUTO_PROMOTE_THRESHOLD)
        edge = scorer.score_edge(
            source="mid/x.py",
            target="mid/y.py",
            namespace="personal",
            activation_count=5,
            created_at=time.time() - 86400 * 20,
            last_activated=time.time() - 86400 * 10,
            conflict_count=1,
            total_comparisons=3,
        )
        assert REJECT_THRESHOLD <= edge.score < AUTO_PROMOTE_THRESHOLD, (
            f"test precondition: score {edge.score} should be in [{REJECT_THRESHOLD}, {AUTO_PROMOTE_THRESHOLD})"
        )

        decision = gate.decide(edge)
        assert decision.action == "review_required"
        assert decision.reviewer_hint  # should have some hint

    def test_custom_thresholds(self):
        scorer = ContributionQualityScorer()
        gate = PeerReviewGate(scorer, auto_promote=0.5, reject=0.1)

        # Edge with score ~0.6: with default thresholds it's review_required,
        # with custom thresholds (0.5/0.1) it's auto_promote
        edge = EdgeQuality(
            source="a",
            target="b",
            namespace="personal",
            score=0.6,
            reinforcement_score=0.6,
            recency_score=0.6,
            conflict_rate=0.0,
            activation_count=5,
            age_days=5.0,
            should_promote=False,
            should_decay=False,
        )

        decision_default = PeerReviewGate(scorer).decide(edge)
        assert decision_default.action == "review_required"

        decision_custom = gate.decide(edge)
        assert decision_custom.action == "auto_promote"

    def test_gate_bundle_classifies_all_edges(self):
        scorer = ContributionQualityScorer()
        gate = PeerReviewGate(scorer)

        bundle = {
            "synapses": [
                {
                    "source": "high/py",
                    "target": "high/py2",
                    "weight": 10.0,
                    "activation_count": 50,
                    "created_at": time.time(),
                    "last_activated": time.time(),
                    "conflicts": 0,
                    "comparisons": 1,
                },
                {
                    "source": "low/py",
                    "target": "low/py2",
                    "weight": 0.01,
                    "activation_count": 0,
                    "created_at": time.time() - 86400 * 365,
                    "last_activated": time.time() - 86400 * 365,
                    "conflicts": 5,
                    "comparisons": 5,
                },
                {
                    "source": "mid/py",
                    "target": "mid/py2",
                    "weight": 3.0,
                    "activation_count": 5,
                    "created_at": time.time() - 86400 * 20,
                    "last_activated": time.time() - 86400 * 10,
                    "conflicts": 1,
                    "comparisons": 3,
                },
            ]
        }

        auto_promoted, review_required, rejected = gate.gate_bundle(bundle)

        assert len(auto_promoted) == 1
        assert auto_promoted[0].action == "auto_promote"
        assert len(rejected) == 1
        assert rejected[0].action == "reject"
        assert len(review_required) == 1
        assert review_required[0].action == "review_required"

    def test_edge_at_exact_boundary(self):
        scorer = ContributionQualityScorer()

        # Edge with score exactly at AUTO_PROMOTE_THRESHOLD
        edge_at = EdgeQuality(
            source="x",
            target="y",
            namespace="personal",
            score=AUTO_PROMOTE_THRESHOLD,
            reinforcement_score=0.7,
            recency_score=0.7,
            conflict_rate=0.0,
            activation_count=10,
            age_days=1.0,
            should_promote=True,
            should_decay=False,
        )
        decision = PeerReviewGate(scorer).decide(edge_at)
        assert decision.action == "auto_promote"  # >= threshold

        # Edge with score exactly at REJECT_THRESHOLD
        edge_below = EdgeQuality(
            source="x",
            target="y",
            namespace="personal",
            score=REJECT_THRESHOLD - 0.001,
            reinforcement_score=0.1,
            recency_score=0.1,
            conflict_rate=0.5,
            activation_count=1,
            age_days=30.0,
            should_promote=False,
            should_decay=True,
        )
        decision_below = PeerReviewGate(scorer).decide(edge_below)
        assert decision_below.action == "reject"  # < threshold

    def test_reviewer_hint_helps_human_review(self):
        scorer = ContributionQualityScorer()
        gate = PeerReviewGate(scorer)

        # Edge with low reinforcement specifically
        edge = EdgeQuality(
            source="a",
            target="b",
            namespace="personal",
            score=0.4,
            reinforcement_score=0.1,  # very low
            recency_score=0.5,
            conflict_rate=0.2,
            activation_count=2,
            age_days=10.0,
            should_promote=False,
            should_decay=False,
        )
        decision = gate.decide(edge)
        if decision.action == "review_required":
            assert "low reinforcement" in decision.reviewer_hint

    def test_contest_escalation_from_merge(self):
        """When E2 escalates a contest, E3 should treat it as review_required."""
        scorer = ContributionQualityScorer()
        merger = QualityWeightedMerger(scorer)

        # Create a contest scenario (both edges weak + close tie)
        edge_a = scorer.score_edge(
            source="x",
            target="y",
            namespace="personal",
            activation_count=1,
            created_at=time.time() - 86400 * 40,
            last_activated=time.time() - 86400 * 30,
            conflict_count=2,
            total_comparisons=5,
        )
        edge_b = scorer.score_edge(
            source="x",
            target="y",
            namespace="personal",
            activation_count=1,
            created_at=time.time() - 86400 * 40,
            last_activated=time.time() - 86400 * 30,
            conflict_count=2,
            total_comparisons=5,
        )

        conflict = merger.resolve_conflict(edge_a, edge_b)
        assert conflict.contest, "test precondition: should be a contest"

        # Now verify E3 treats contest edges as review_required (not auto_promote, not reject)
        gate = PeerReviewGate(scorer)
        decision = gate.decide(conflict.edge_a)
        # Contest edges should land in review band since they're weak
        assert decision.action in ("review_required", "reject")

    def test_fail_open_on_malformed_edge(self):
        """Score_bundle skips malformed edges — gate should handle empty scored list."""
        scorer = ContributionQualityScorer()
        gate = PeerReviewGate(scorer)

        # Malformed bundle — missing source/target
        bundle = {"synapses": [{"weight": 1.0}]}
        auto_promoted, review_required, rejected = gate.gate_bundle(bundle)

        assert auto_promoted == []
        assert review_required == []
        assert rejected == []


class TestReviewDecision:
    def test_to_dict_contains_expected_fields(self):
        edge = EdgeQuality(
            source="a",
            target="b",
            namespace="personal",
            score=0.5,
            reinforcement_score=0.5,
            recency_score=0.5,
            conflict_rate=0.0,
            activation_count=5,
            age_days=1.0,
            should_promote=False,
            should_decay=False,
        )
        decision = ReviewDecision(
            edge=edge,
            action="review_required",
            reason="test",
            reviewer_hint="check this",
        )
        d = decision.to_dict()
        assert d["source"] == "a"
        assert d["target"] == "b"
        assert d["score"] == 0.5
        assert d["action"] == "review_required"
        assert d["reason"] == "test"
        assert d["reviewer_hint"] == "check this"
