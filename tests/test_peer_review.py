"""Tests for E3 — peer review gate."""
import time
from neuralmind.contribution_scoring import EdgeQuality
from neuralmind.peer_review import PeerReviewGate, AUTO_PROMOTE_THRESHOLD, REJECT_THRESHOLD


class TestPeerReviewGate:
    def test_auto_promotes_high_quality(self):
        gate = PeerReviewGate(auto_promote=0.75, reject=0.15)
        edge = EdgeQuality(
            source="a", target="b", namespace="shared",
            score=0.9, reinforcement_score=0.9, recency_score=0.9,
            conflict_rate=0.0, activation_count=50, age_days=1.0,
            should_promote=True, should_decay=False,
        )
        decision = gate.decide(edge)
        assert decision.action == "auto_promote"

    def test_rejects_low_quality(self):
        gate = PeerReviewGate(auto_promote=0.75, reject=0.15)
        edge = EdgeQuality(
            source="a", target="b", namespace="personal",
            score=0.1, reinforcement_score=0.1, recency_score=0.1,
            conflict_rate=0.9, activation_count=1, age_days=100.0,
            should_promote=False, should_decay=True,
        )
        decision = gate.decide(edge)
        assert decision.action == "reject"

    def test_marginal_flags_review(self):
        gate = PeerReviewGate(auto_promote=0.8, reject=0.15)
        edge = EdgeQuality(
            source="a", target="b", namespace="personal",
            score=0.5, reinforcement_score=0.5, recency_score=0.5,
            conflict_rate=0.3, activation_count=5, age_days=14.0,
            should_promote=False, should_decay=False,
        )
        decision = gate.decide(edge)
        assert decision.action == "review_required"

    def test_gates_bundle(self):
        gate = PeerReviewGate(auto_promote=0.7, reject=0.2)
        bundle = {
            "synapses": [
                {"source": "hot", "target": "edge", "activation_count": 50,
                 "created_at": time.time() - 86400, "last_activated": time.time(),
                 "weight": 0.9, "conflicts": 0, "comparisons": 10},
                {"source": "mid", "target": "edge", "activation_count": 10,
                 "created_at": time.time() - 86400 * 20, "last_activated": time.time() - 86400 * 5,
                 "weight": 0.5, "conflicts": 2, "comparisons": 5},
                {"source": "cold", "target": "edge", "activation_count": 1,
                 "created_at": time.time() - 86400 * 90, "last_activated": time.time() - 86400 * 80,
                 "weight": 0.05, "conflicts": 5, "comparisons": 5},
            ]
        }
        auto, review, reject = gate.gate_bundle(bundle)
        assert len(auto) > 0
        assert len(reject) > 0
