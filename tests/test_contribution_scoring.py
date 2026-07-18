"""Tests for E1 — contribution-quality scoring."""

import time

from neuralmind.contribution_scoring import ContributionQualityScorer


class TestContributionQualityScorer:
    def test_high_quality_edge(self):
        scorer = ContributionQualityScorer()
        edge = scorer.score_edge(
            source="a",
            target="b",
            namespace="personal",
            activation_count=30,
            created_at=time.time() - 86400,
            last_activated=time.time(),
            conflict_count=0,
            total_comparisons=5,
        )
        assert edge.score > 0.5
        assert edge.should_promote or not edge.should_decay

    def test_stale_edge_decays(self):
        scorer = ContributionQualityScorer()
        edge = scorer.score_edge(
            source="a",
            target="b",
            namespace="personal",
            activation_count=1,
            created_at=time.time() - 86400 * 100,
            last_activated=time.time() - 86400 * 90,
            conflict_count=5,
            total_comparisons=5,
        )
        assert edge.should_decay
        assert edge.recency_score < 0.2

    def test_neutral_edge(self):
        scorer = ContributionQualityScorer()
        edge = scorer.score_edge(
            source="a",
            target="b",
            namespace="personal",
            activation_count=5,
            created_at=time.time() - 86400 * 30,
            last_activated=time.time() - 86400 * 14,
            conflict_count=1,
            total_comparisons=5,
        )
        assert not edge.should_promote and not edge.should_decay


class TestBundleScoring:
    def test_classify_bundle(self):
        scorer = ContributionQualityScorer()
        bundle = {
            "synapses": [
                {
                    "source": "hot",
                    "target": "edge",
                    "activation_count": 50,
                    "created_at": time.time() - 86400,
                    "last_activated": time.time(),
                    "weight": 0.9,
                    "conflicts": 0,
                    "comparisons": 10,
                },
                {
                    "source": "cold",
                    "target": "edge",
                    "activation_count": 1,
                    "created_at": time.time() - 86400 * 100,
                    "last_activated": time.time() - 86400 * 90,
                    "weight": 0.1,
                    "conflicts": 5,
                    "comparisons": 5,
                },
            ]
        }
        promote, neutral, decay = scorer.classify_bundle(bundle)
        assert len(promote) > 0 or len(decay) > 0
