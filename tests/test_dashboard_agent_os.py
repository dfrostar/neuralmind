"""Tests for dashboard.py Agent OS sections wiring."""

from __future__ import annotations

from pathlib import Path

import pytest

from neuralmind.dashboard import (
    agent_os_experiments,
    agent_os_signals,
    agent_os_tenants,
    full_dashboard,
)


# ---------------------------------------------------------------------------
# agent_os_tenants
# ---------------------------------------------------------------------------


class TestAgentOSTenants:
    def test_empty(self, tmp_path, monkeypatch):
        monkeypatch.setenv("NEURALMIND_TENANTS_DIR", str(tmp_path))
        result = agent_os_tenants()
        assert result["total_tenants"] == 0
        assert result["tiers"] == {}
        assert result["recent"] == []

    def test_with_tenants(self, tmp_path, monkeypatch):
        from neuralmind.agent_os import TenantRegistry

        monkeypatch.setenv("NEURALMIND_TENANTS_DIR", str(tmp_path))
        reg = TenantRegistry(tmp_path)
        reg.create_tenant("acme", "Acme Corp", admin_email="alice@example.com")
        reg.create_tenant("zebra", "Zebra Inc", admin_email="bob@example.com")

        result = agent_os_tenants(tenants_dir=tmp_path)
        assert result["total_tenants"] == 2
        assert result["has_data"] is True


# ---------------------------------------------------------------------------
# agent_os_signals (wired to shared instance)
# ---------------------------------------------------------------------------


class TestAgentOSSignals:
    def test_no_detector(self):
        """Without a signal detector, returns empty summary."""
        result = agent_os_signals()
        assert result["tracked_metrics"] == 0
        assert result["has_data"] is False

    def test_with_detector(self, tmp_path):
        """With a shared detector, returns real data."""
        from neuralmind.agent_os import RootCauseCorrelator, SignalDetector

        correlator = RootCauseCorrelator()
        detector = SignalDetector(correlator=correlator)

        # Push some values to create state
        for _ in range(10):
            detector.push("latency_ms", 100.0)

        result = agent_os_signals(signal_detector=detector)
        assert result["tracked_metrics"] == 1
        assert "latency_ms" in result["metrics"]
        assert result["has_data"] is True

    def test_detector_with_signals(self):
        """Detector with actual signals reflects fired signals."""
        from neuralmind.agent_os import RootCauseCorrelator, SignalDetector

        correlator = RootCauseCorrelator()
        detector = SignalDetector(correlator=correlator)

        # Warm up + shift to trigger signal
        for _ in range(50):
            detector.push("latency_ms", 100.0)
        for _ in range(50):
            result = detector.push("latency_ms", 200.0)
            if result.signal:
                break

        result = agent_os_signals(signal_detector=detector)
        assert result["tracked_metrics"] >= 1


# ---------------------------------------------------------------------------
# agent_os_experiments (wired to shared instance)
# ---------------------------------------------------------------------------


class TestAgentOSExperiments:
    def test_no_engine(self):
        """Without a promotion engine, returns empty summary."""
        result = agent_os_experiments()
        assert result["total_experiments"] == 0
        assert result["has_data"] is False

    def test_with_engine(self, tmp_path):
        """With a shared engine, returns real data."""
        from neuralmind.agent_os import ExperimentRunner, PromotionEngine

        engine = PromotionEngine()
        engine.run("p1", "m", 100.0, 90.0)

        result = agent_os_experiments(promotion_engine=engine)
        assert result["total_experiments"] == 1
        assert result["has_data"] is True


# ---------------------------------------------------------------------------
# full_dashboard with agent_os_context
# ---------------------------------------------------------------------------


class TestFullDashboardAgentOS:
    def test_without_context(self, tmp_path):
        """full_dashboard without agent_os_context falls back to empty data."""
        result = full_dashboard(project_path=tmp_path)
        assert "agent_os" in result
        assert result["agent_os"]["signals"]["tracked_metrics"] == 0
        assert result["agent_os"]["experiments"]["total_experiments"] == 0

    def test_with_context(self, tmp_path, monkeypatch):
        """full_dashboard with agent_os_context shows real data."""
        from neuralmind.agent_os import (
            PromotionEngine,
            RootCauseCorrelator,
            SignalDetector,
            TenantRegistry,
        )

        monkeypatch.setenv("NEURALMIND_TENANTS_DIR", str(tmp_path))

        correlator = RootCauseCorrelator()
        detector = SignalDetector(correlator=correlator)
        engine = PromotionEngine()

        # Create some state
        detector.push("latency_ms", 100.0)
        engine.run("p1", "m", 100.0, 90.0)

        ctx = {
            "signal_detector": detector,
            "promotion_engine": engine,
        }

        result = full_dashboard(project_path=tmp_path, agent_os_context=ctx)
        assert result["agent_os"]["signals"]["tracked_metrics"] == 1
        assert result["agent_os"]["experiments"]["total_experiments"] == 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
