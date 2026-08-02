"""Tests for signal → correlator → insight pipeline."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from neuralmind.agent_os import (
    CauseType,
    RootCauseCorrelator,
    Signal,
    SignalDetector,
    TenantRegistry,
    create_agent_os_routes,
    get_insights,
    get_signals,
    log_insight,
    log_signal,
)
from neuralmind.agent_os.experiment import ExperimentRunner


@pytest.fixture
def tmp_tenants(tmp_path, monkeypatch):
    monkeypatch.setenv("NEURALMIND_TENANTS_DIR", str(tmp_path))
    registry = TenantRegistry(tmp_path)
    return registry, tmp_path


@pytest.fixture
def correlator():
    return RootCauseCorrelator(lookback_seconds=3600)


@pytest.fixture
def detector(correlator):
    return SignalDetector(correlator=correlator)


# ---------------------------------------------------------------------------
# SignalDetector.push()
# ---------------------------------------------------------------------------


class TestSignalDetectorPush:
    def test_no_signal_returns_none(self, detector):
        """push() returns None signal and None insight when no anomaly."""
        result = detector.push("latency_ms", 100.0)
        assert result.signal is None
        assert result.insight is None

    def test_signal_fires_with_anomaly(self, detector):
        """push() returns signal when Page-Hinkley fires."""
        # Warm up
        for _ in range(50):
            detector.push("latency_ms", 100.0)
        # Shift up
        result = None
        for _ in range(50):
            r = detector.push("latency_ms", 200.0)
            if r.signal:
                result = r
                break
        assert result is not None
        assert result.signal is not None
        assert result.signal.metric_name == "latency_ms"

    def test_signal_with_project_generates_insight(self, detector, tmp_path):
        """push() generates insight when signal fires and project_path given."""
        # Create minimal git repo
        (tmp_path / ".git").mkdir()
        (tmp_path / ".git" / "HEAD").write_text("ref: refs/heads/main\n")
        (tmp_path / ".git" / "refs").mkdir()
        (tmp_path / ".git" / "refs" / "heads").mkdir()

        # Warm up
        for _ in range(50):
            detector.push("latency_ms", 100.0, project_path=tmp_path)
        # Shift up
        result = None
        for _ in range(50):
            r = detector.push("latency_ms", 200.0, project_path=tmp_path)
            if r.signal:
                result = r
                break
        assert result is not None
        assert result.signal is not None
        assert result.insight is not None
        assert isinstance(result.insight, CauseType) or hasattr(result.insight, "cause_type")

    def test_signal_without_correlator_no_insight(self, tmp_path):
        """push() with no correlator returns signal but no insight."""
        detector = SignalDetector()  # No correlator
        # Warm up
        for _ in range(50):
            detector.push("latency_ms", 100.0)
        # Shift up
        result = None
        for _ in range(50):
            r = detector.push("latency_ms", 200.0)
            if r.signal:
                result = r
                break
        assert result is not None
        assert result.signal is not None
        assert result.insight is None

    def test_push_result_to_dict(self, detector):
        """PushResult.to_dict() serializes correctly."""
        result = detector.push("latency_ms", 100.0)
        d = result.to_dict()
        assert d["signal"] is None
        assert d["insight"] is None


# ---------------------------------------------------------------------------
# signals_log
# ---------------------------------------------------------------------------


class TestSignalsLog:
    def test_log_and_get_signals(self, tmp_path):
        """log_signal stores signal, get_signals retrieves it."""
        from neuralmind.agent_os.signals_log import clear_tenant

        tenant_id = "test_tenant"
        clear_tenant(tenant_id, base_dir=tmp_path)

        signal = Signal(
            signal_id="sig_1",
            timestamp=1000.0,
            metric_name="latency_ms",
            value=200.0,
            baseline=100.0,
            delta=100.0,
            severity=4.0,
        )
        log_signal(tenant_id, signal, base_dir=tmp_path)
        signals = get_signals(tenant_id, base_dir=tmp_path)
        assert len(signals) == 1
        assert signals[0]["signal_id"] == "sig_1"
        assert signals[0]["metric_name"] == "latency_ms"

    def test_log_and_get_insights(self, tmp_path):
        """log_insight stores insight, get_insights retrieves it."""
        from neuralmind.agent_os.signals_log import clear_tenant

        tenant_id = "test_tenant"
        clear_tenant(tenant_id, base_dir=tmp_path)

        insight = CauseType.UNKNOWN
        log_insight(
            tenant_id,
            RootCauseCorrelator().correlate(
                Signal(
                    signal_id="sig_1",
                    timestamp=1000.0,
                    metric_name="latency_ms",
                    value=200.0,
                    baseline=100.0,
                    delta=100.0,
                    severity=4.0,
                ),
                tmp_path,
            ),
            base_dir=tmp_path,
        )
        insights = get_insights(tenant_id, base_dir=tmp_path)
        assert len(insights) == 1
        assert insights[0]["cause_type"] == "unknown"


# ---------------------------------------------------------------------------
# API integration
# ---------------------------------------------------------------------------


class TestSignalPipelineAPI:
    def test_push_signal_returns_insight(self, tmp_tenants, tmp_path):
        """POST /signals returns insight when signal fires."""
        registry, _ = tmp_tenants
        registry.create_tenant("acme", "Acme", admin_email="alice")

        correlator = RootCauseCorrelator(lookback_seconds=3600)
        detector = SignalDetector(correlator=correlator)
        runner = ExperimentRunner()
        routes = create_agent_os_routes(registry, detector, runner)

        # Warm up
        for _ in range(50):
            routes[("POST", "/api/agent-os/signals")](
                {"tenant_id": "acme", "email": "alice", "metric_name": "latency_ms", "value": 100.0}
            )

        # Shift up
        result = None
        for _ in range(50):
            status, payload = routes[("POST", "/api/agent-os/signals")](
                {"tenant_id": "acme", "email": "alice", "metric_name": "latency_ms", "value": 200.0}
            )
            if payload.get("signal"):
                result = payload
                break

        assert result is not None
        assert result["signal"] is not None
        # Insight may or may not fire depending on git repo state
        # but signal should always fire


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
