"""Tests for ship_callable production wiring and MIN_SIGNALS gate."""

from __future__ import annotations

import pytest

from neuralmind.agent_os import (
    ExperimentStatus,
    MIN_SIGNALS_BEFORE_AUTO_PROMOTE,
    PromotionEngine,
    Proposal,
    TunerIncumbent,
)


# ---------------------------------------------------------------------------
# TunerIncumbent
# ---------------------------------------------------------------------------


class TestTunerIncumbent:
    def test_create(self):
        t = TunerIncumbent("latency_ms", 840.0, tag="v1.2.3")
        assert t.metric_name == "latency_ms"
        assert t.value == 840.0
        assert t.tag == "v1.2.3"

    def test_update(self):
        t = TunerIncumbent("latency_ms", 840.0, tag="v1.2.3")
        t.update(810.0, "v1.3.0-rc1", "Promoted exp_123")
        assert t.value == 810.0
        assert t.tag == "v1.3.0-rc1"

    def test_update_history(self):
        t = TunerIncumbent("latency_ms", 840.0, tag="v1.2.3")
        t.update(810.0, "v1.3.0-rc1", "Promoted exp_123")
        t.update(800.0, "v1.3.0-rc2", "Promoted exp_456")
        history = t.get_history()
        assert len(history) == 2
        # Newest first
        assert history[0]["to_tag"] == "v1.3.0-rc2"
        assert history[1]["to_tag"] == "v1.3.0-rc1"

    def test_history_is_reversed(self):
        t = TunerIncumbent("m", 100.0)
        t.update(90.0, "v2", "test")
        t.update(80.0, "v3", "test")
        h = t.get_history()
        assert h[0]["to_tag"] == "v3"
        assert h[1]["to_tag"] == "v2"


# ---------------------------------------------------------------------------
# Proposal
# ---------------------------------------------------------------------------


class TestProposal:
    def test_create(self):
        p = Proposal(
            proposal_id="prop_123",
            title="Optimize latency",
            hypothesis="Reduce buffer size",
            baseline_tag="v1.2.3",
            candidate_tag="v1.3.0-rc1",
            metric_name="latency_ms",
            baseline_value=840.0,
            candidate_value=790.0,
        )
        assert p.proposal_id == "prop_123"
        assert p.baseline_tag == "v1.2.3"
        assert p.candidate_tag == "v1.3.0-rc1"
        assert p.status == "proposed"

    def test_to_dict(self):
        p = Proposal(
            proposal_id="prop_123",
            title="Test",
            hypothesis="Test",
            baseline_tag="v1",
            candidate_tag="v2",
            metric_name="m",
            baseline_value=100.0,
            candidate_value=90.0,
        )
        d = p.to_dict()
        assert d["baseline_tag"] == "v1"
        assert d["candidate_tag"] == "v2"
        assert d["status"] == "proposed"


# ---------------------------------------------------------------------------
# ship_callable + MIN_SIGNALS gate
# ---------------------------------------------------------------------------


class TestPromotionEngineWiring:
    def test_promote_updates_incumbent(self):
        """PROMOTED verdict updates incumbent value + tag."""
        incumbent = TunerIncumbent("latency_ms", 840.0, tag="v1.2.3")
        proposal = Proposal(
            proposal_id="prop_123",
            title="Test",
            hypothesis="Test",
            baseline_tag="v1.2.3",
            candidate_tag="v1.3.0-rc1",
            metric_name="latency_ms",
            baseline_value=840.0,
            candidate_value=790.0,  # ~5.95% improvement
        )
        engine = PromotionEngine(
            incumbent=incumbent,
            proposal=proposal,
            signal_count=MIN_SIGNALS_BEFORE_AUTO_PROMOTE,
        )
        result = engine.run()
        assert result.verdict == ExperimentStatus.PROMOTED
        assert incumbent.value == 790.0
        assert incumbent.tag == "v1.3.0-rc1"
        assert proposal.status == "promoted"

    def test_rollback_reverts_to_baseline(self):
        """ROLLED_BACK verdict reverts to baseline value + tag."""
        incumbent = TunerIncumbent("latency_ms", 840.0, tag="v1.2.3")
        proposal = Proposal(
            proposal_id="prop_123",
            title="Test",
            hypothesis="Test",
            baseline_tag="v1.2.3",
            candidate_tag="v1.3.0-rc1",
            metric_name="latency_ms",
            baseline_value=840.0,
            candidate_value=900.0,  # regression
        )
        engine = PromotionEngine(
            incumbent=incumbent,
            proposal=proposal,
            signal_count=MIN_SIGNALS_BEFORE_AUTO_PROMOTE,
        )
        result = engine.run()
        assert result.verdict == ExperimentStatus.ROLLED_BACK
        assert incumbent.value == 840.0
        assert incumbent.tag == "v1.2.3"
        assert proposal.status == "rolled_back"

    def test_min_signals_gate_blocks_promotion(self):
        """Auto-promote blocked when signal_count < MIN_SIGNALS_BEFORE_AUTO_PROMOTE."""
        incumbent = TunerIncumbent("latency_ms", 840.0, tag="v1.2.3")
        proposal = Proposal(
            proposal_id="prop_123",
            title="Test",
            hypothesis="Test",
            baseline_tag="v1.2.3",
            candidate_tag="v1.3.0-rc1",
            metric_name="latency_ms",
            baseline_value=840.0,
            candidate_value=790.0,
        )
        engine = PromotionEngine(
            incumbent=incumbent,
            proposal=proposal,
            signal_count=MIN_SIGNALS_BEFORE_AUTO_PROMOTE - 1,  # insufficient
        )
        result = engine.run()
        assert result.verdict == ExperimentStatus.PROMOTED
        # Incumbent should NOT be updated
        assert incumbent.value == 840.0
        assert incumbent.tag == "v1.2.3"

    def test_min_signals_gate_allows_promotion(self):
        """Auto-promote fires when signal_count >= MIN_SIGNALS_BEFORE_AUTO_PROMOTE."""
        incumbent = TunerIncumbent("latency_ms", 840.0, tag="v1.2.3")
        proposal = Proposal(
            proposal_id="prop_123",
            title="Test",
            hypothesis="Test",
            baseline_tag="v1.2.3",
            candidate_tag="v1.3.0-rc1",
            metric_name="latency_ms",
            baseline_value=840.0,
            candidate_value=790.0,
        )
        engine = PromotionEngine(
            incumbent=incumbent,
            proposal=proposal,
            signal_count=MIN_SIGNALS_BEFORE_AUTO_PROMOTE,
        )
        result = engine.run()
        assert result.verdict == ExperimentStatus.PROMOTED
        # Incumbent SHOULD be updated
        assert incumbent.value == 790.0

    def test_rejected_verdict_no_update(self):
        """REJECTED verdict does not update incumbent."""
        incumbent = TunerIncumbent("latency_ms", 840.0, tag="v1.2.3")
        proposal = Proposal(
            proposal_id="prop_123",
            title="Test",
            hypothesis="Test",
            baseline_tag="v1.2.3",
            candidate_tag="v1.3.0-rc1",
            metric_name="latency_ms",
            baseline_value=840.0,
            candidate_value=835.0,  # too small an improvement
        )
        engine = PromotionEngine(
            incumbent=incumbent,
            proposal=proposal,
            signal_count=MIN_SIGNALS_BEFORE_AUTO_PROMOTE,
        )
        result = engine.run()
        assert result.verdict == ExperimentStatus.REJECTED
        assert incumbent.value == 840.0

    def test_custom_ship_callable(self):
        """Custom ship_callable is invoked on PROMOTED."""
        called = []

        def custom_ship(result):
            called.append(result)

        engine = PromotionEngine(
            ship_callable=custom_ship,
            signal_count=MIN_SIGNALS_BEFORE_AUTO_PROMOTE,
        )
        result = engine.run(
            proposal_id="p1",
            metric_name="latency_ms",
            baseline_value=100.0,
            candidate_value=90.0,  # 10% improvement
        )
        assert result.verdict == ExperimentStatus.PROMOTED
        assert len(called) == 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
