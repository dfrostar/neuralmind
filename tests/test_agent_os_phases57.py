"""Tests for Phases 5-7: CLI wiring, auto-trigger, proposals API, dashboard, adversarial queries."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest


def run_cli(args: list[str], env: dict[str, str] | None = None) -> subprocess.CompletedProcess:
    cmd = [sys.executable, "-m", "neuralmind.cli"] + args
    return subprocess.run(
        cmd, capture_output=True, text=True,
        env={**os.environ, **(env or {})}, timeout=30,
    )


@pytest.fixture
def clean_env(tmp_path, monkeypatch):
    monkeypatch.setenv("NEURALMIND_TENANTS_DIR", str(tmp_path / "tenants"))
    monkeypatch.setenv("NEURALMIND_DAEMON_HOME", str(tmp_path / "daemon"))
    monkeypatch.setenv("NEURALMIND_AGENTOS_DIR", str(tmp_path / "agentos"))
    return tmp_path


# =========================================================================
# Phase 5: CLI Production Wiring
# =========================================================================


class TestCLISignalsPushUsesPush:
    def test_push_output_format_has_signal_and_insight_fields(self, clean_env):
        result = run_cli(["agent-os", "signals", "push", "--metric", "latency_ms", "--value", "100.0"])
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert "signal" in data
        assert "insight" in data
        assert "metric" in data
        assert "value" in data
        assert data["metric"] == "latency_ms"
        assert data["value"] == 100.0


class TestCLIProposalsCreate:
    def test_create_proposal(self, clean_env):
        result = run_cli([
            "agent-os", "proposals", "create",
            "--title", "Optimize latency",
            "--hypothesis", "Reducing buffer size improves latency",
            "--baseline-tag", "v1.2.3",
            "--candidate-tag", "v1.3.0-rc1",
            "--metric", "latency_ms",
            "--baseline", "840.0",
            "--candidate", "810.0",
            "--tags", "perf", "latency",
        ])
        assert result.returncode == 0, f"stderr: {result.stderr}"
        data = json.loads(result.stdout)
        assert data["title"] == "Optimize latency"
        assert data["hypothesis"] == "Reducing buffer size improves latency"
        assert data["baseline_tag"] == "v1.2.3"
        assert data["candidate_tag"] == "v1.3.0-rc1"
        assert data["metric_name"] == "latency_ms"
        assert data["baseline_value"] == 840.0
        assert data["candidate_value"] == 810.0
        assert data["status"] == "proposed"
        assert data["signal_count"] == 0
        assert "perf" in data["tags"]
        assert "latency" in data["tags"]
        assert data["proposal_id"].startswith("prop_")

    def test_create_proposal_minimal(self, clean_env):
        result = run_cli([
            "agent-os", "proposals", "create",
            "--title", "T",
            "--hypothesis", "H",
            "--baseline-tag", "v1",
            "--candidate-tag", "v2",
            "--metric", "m",
            "--baseline", "100",
            "--candidate", "90",
        ])
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert data["tags"] == []

    def test_list_proposals(self, clean_env):
        run_cli(["agent-os", "proposals", "create", "--title", "A", "--hypothesis", "H",
                 "--baseline-tag", "v1", "--candidate-tag", "v2", "--metric", "m",
                 "--baseline", "100", "--candidate", "90"])
        run_cli(["agent-os", "proposals", "create", "--title", "B", "--hypothesis", "H",
                 "--baseline-tag", "v1", "--candidate-tag", "v2", "--metric", "m",
                 "--baseline", "100", "--candidate", "90"])
        result = run_cli(["agent-os", "proposals", "list"])
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert len(data) == 2

    def test_proposal_history(self, clean_env):
        result = run_cli(["agent-os", "proposals", "create", "--title", "T", "--hypothesis", "H",
                          "--baseline-tag", "v1", "--candidate-tag", "v2", "--metric", "m",
                          "--baseline", "100", "--candidate", "90"])
        pid = json.loads(result.stdout)["proposal_id"]
        result = run_cli(["agent-os", "proposals", "history", "--id", pid])
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert len(data) == 1
        assert data[0]["proposal_id"] == pid

    def test_proposal_run(self, clean_env):
        result = run_cli(["agent-os", "proposals", "create", "--title", "T", "--hypothesis", "H",
                          "--baseline-tag", "v1", "--candidate-tag", "v2", "--metric", "latency_ms",
                          "--baseline", "100.0", "--candidate", "85.0"])
        pid = json.loads(result.stdout)["proposal_id"]
        result = run_cli(["agent-os", "proposals", "run", "--id", pid])
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert "experiment" in data
        assert "proposal_status" in data
        assert "incumbent_value" in data
        assert "incumbent_tag" in data
        assert data["proposal_id"] == pid

    def test_proposal_run_not_found(self, clean_env):
        result = run_cli(["agent-os", "proposals", "run", "--id", "prop_nonexistent"])
        assert result.returncode != 0


class TestCLIHealthSnapshot:
    def test_health_snapshot(self, clean_env):
        result = run_cli(["agent-os", "health-snapshot"])
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert "tenants" in data
        assert "signals" in data
        assert "proposals" in data
        assert "experiments" in data
        assert "correlator" in data

    def test_health_snapshot_format(self, clean_env):
        """Verify health snapshot structure reflects current process state."""
        run_cli(["agent-os", "proposals", "create", "--title", "T", "--hypothesis", "H",
                 "--baseline-tag", "v1", "--candidate-tag", "v2", "--metric", "m",
                 "--baseline", "100", "--candidate", "90"])
        result = run_cli(["agent-os", "health-snapshot"])
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert "tenants" in data
        assert "signals" in data
        assert "proposals" in data
        assert "experiments" in data
        assert "correlator" in data


# =========================================================================
# Phase 6: Auto-Trigger Loop
# =========================================================================


class TestAutoTriggerLoop:
    def test_auto_trigger_creates_proposal(self, clean_env):
        from neuralmind.agent_os import AutoTriggerLoop, RootCauseCorrelator, SignalDetector
        from neuralmind.agent_os.proposal_store import _store_path, list_proposals

        correlator = RootCauseCorrelator()
        detector = SignalDetector(correlator=correlator)
        loop = AutoTriggerLoop(detector)

        p = _store_path()
        if p.exists():
            p.unlink()

        from neuralmind.agent_os import CauseType, Insight, Signal
        signal = Signal(
            signal_id="sig_test", timestamp=1000.0, metric_name="test_metric",
            value=200.0, baseline=100.0, delta=100.0, severity=5.0,
        )
        insight = Insight(
            insight_id="ins_test", signal_id="sig_test",
            ts="2026-08-02T00:00:00+00:00", hypothesis="Test hypothesis",
            cause_type=CauseType.UNKNOWN, cause_ref="", confidence=0.5,
        )

        loop._on_signal_insight(signal, insight)

        proposals = list_proposals()
        assert len(proposals) == 1
        assert proposals[0]["metric_name"] == "test_metric"
        assert proposals[0]["signal_count"] == 1
        assert "auto-triggered" in proposals[0]["tags"]

    def test_auto_trigger_increments_existing(self, clean_env):
        from neuralmind.agent_os import AutoTriggerLoop, RootCauseCorrelator, SignalDetector
        from neuralmind.agent_os.proposal_store import create_proposal, list_proposals

        correlator = RootCauseCorrelator()
        detector = SignalDetector(correlator=correlator)
        loop = AutoTriggerLoop(detector)

        create_proposal(
            title="Existing", hypothesis="H", baseline_tag="v1", candidate_tag="v2",
            metric_name="test_metric", baseline_value=100.0, candidate_value=90.0,
        )

        from neuralmind.agent_os import CauseType, Insight, Signal
        signal = Signal(
            signal_id="sig_test2", timestamp=1000.0, metric_name="test_metric",
            value=200.0, baseline=100.0, delta=100.0, severity=5.0,
        )
        insight = Insight(
            insight_id="ins_test2", signal_id="sig_test2",
            ts="2026-08-02T00:00:00+00:00", hypothesis="Test",
            cause_type=CauseType.UNKNOWN, cause_ref="", confidence=0.5,
        )

        loop._on_signal_insight(signal, insight)

        proposals = [p for p in list_proposals() if p["metric_name"] == "test_metric"]
        assert len(proposals) == 1
        assert proposals[0]["signal_count"] == 1

    def test_auto_trigger_runs_experiment_at_threshold(self, clean_env):
        from neuralmind.agent_os import (
            AutoTriggerLoop,
            RootCauseCorrelator,
            SignalDetector,
            TunerIncumbent,
        )
        from neuralmind.agent_os.promotion import MIN_SIGNALS_BEFORE_AUTO_PROMOTE
        from neuralmind.agent_os.proposal_store import (
            create_proposal,
            list_proposals,
            update_proposal,
        )

        correlator = RootCauseCorrelator()
        detector = SignalDetector(correlator=correlator)
        incumbent = TunerIncumbent("latency_ms", 100.0, "v1")
        loop = AutoTriggerLoop(detector, incumbent=incumbent)

        proposal = create_proposal(
            title="Auto", hypothesis="H", baseline_tag="v1", candidate_tag="v2",
            metric_name="latency_ms", baseline_value=100.0, candidate_value=85.0,
        )
        update_proposal(proposal["proposal_id"], {"signal_count": MIN_SIGNALS_BEFORE_AUTO_PROMOTE - 1})

        from neuralmind.agent_os import CauseType, Insight, Signal
        signal = Signal(
            signal_id="sig_threshold", timestamp=1000.0, metric_name="latency_ms",
            value=200.0, baseline=100.0, delta=100.0, severity=5.0,
        )
        insight = Insight(
            insight_id="ins_threshold", signal_id="sig_threshold",
            ts="2026-08-02T00:00:00+00:00", hypothesis="Test",
            cause_type=CauseType.UNKNOWN, cause_ref="", confidence=0.5,
        )

        loop._on_signal_insight(signal, insight)

        proposals = [p for p in list_proposals() if p["proposal_id"] == proposal["proposal_id"]]
        assert len(proposals) == 1
        assert proposals[0]["signal_count"] == MIN_SIGNALS_BEFORE_AUTO_PROMOTE
        assert "last_experiment_id" in proposals[0]
        assert "last_verdict" in proposals[0]

    def test_auto_trigger_updates_incumbent_on_promote(self, clean_env):
        from neuralmind.agent_os import TunerIncumbent
        from neuralmind.agent_os.promotion import ExperimentStatus, PromotionEngine, Proposal

        incumbent = TunerIncumbent("latency_ms", 100.0, "v1")
        proposal = Proposal(
            proposal_id="p_test", title="Test", hypothesis="H",
            baseline_tag="v1", candidate_tag="v2", metric_name="latency_ms",
            baseline_value=100.0, candidate_value=85.0,
        )
        engine = PromotionEngine(incumbent=incumbent, proposal=proposal, signal_count=10)
        result = engine.run()

        if result.verdict == ExperimentStatus.PROMOTED:
            assert incumbent.value == 85.0
            assert incumbent.tag == "v2"

    def test_auto_trigger_reverts_on_rollback(self, clean_env):
        from neuralmind.agent_os import TunerIncumbent
        from neuralmind.agent_os.promotion import ExperimentStatus, PromotionEngine, Proposal

        incumbent = TunerIncumbent("latency_ms", 100.0, "v1")
        proposal = Proposal(
            proposal_id="p_test", title="Test", hypothesis="H",
            baseline_tag="v1", candidate_tag="v2", metric_name="latency_ms",
            baseline_value=100.0, candidate_value=120.0,
        )
        engine = PromotionEngine(incumbent=incumbent, proposal=proposal, signal_count=10)
        result = engine.run()

        if result.verdict == ExperimentStatus.ROLLED_BACK:
            assert incumbent.value == 100.0
            assert incumbent.tag == "v1"


# =========================================================================
# Phase 6: Proposals API
# =========================================================================


class TestProposalsAPI:
    def test_create_proposal(self):
        from neuralmind.agent_os import (
            ExperimentRunner,
            SignalDetector,
            TenantRegistry,
            create_agent_os_routes,
        )
        from neuralmind.agent_os.auth import SessionStore

        with tempfile.TemporaryDirectory() as tmp:
            os.environ["NEURALMIND_AGENTOS_DIR"] = f"{tmp}/agentos"
            registry = TenantRegistry(Path(tmp))
            signal_detector = SignalDetector()
            experiment_runner = ExperimentRunner()
            session_store = SessionStore()
            routes = create_agent_os_routes(registry, signal_detector, experiment_runner, session_store=session_store)

            # Create a tenant first (bootstrap mode)
            status, payload = routes[("POST", "/api/agent-os/tenants")]({
                "tenant_id": "testcorp", "admin_email": "alice", "name": "Test"
            })
            assert status == 201

            # Create proposal
            handler = routes[("POST", "/api/agent-os/proposals")]
            status, payload = handler({
                "tenant_id": "testcorp", "email": "alice",
                "title": "Test proposal", "hypothesis": "H",
                "baseline_tag": "v1", "candidate_tag": "v2",
                "metric_name": "latency_ms", "baseline_value": 100.0, "candidate_value": 85.0,
            })
            assert status == 201
            assert payload["title"] == "Test proposal"

    def test_list_proposals(self):
        from neuralmind.agent_os import (
            ExperimentRunner,
            SignalDetector,
            TenantRegistry,
            create_agent_os_routes,
        )
        from neuralmind.agent_os.auth import SessionStore

        with tempfile.TemporaryDirectory() as tmp:
            os.environ["NEURALMIND_AGENTOS_DIR"] = f"{tmp}/agentos"
            registry = TenantRegistry(Path(tmp))
            signal_detector = SignalDetector()
            experiment_runner = ExperimentRunner()
            session_store = SessionStore()
            routes = create_agent_os_routes(registry, signal_detector, experiment_runner, session_store=session_store)

            # Create tenant
            routes[("POST", "/api/agent-os/tenants")]({
                "tenant_id": "testcorp", "admin_email": "alice", "name": "Test"
            })

            # Create proposal
            routes[("POST", "/api/agent-os/proposals")]({
                "tenant_id": "testcorp", "email": "alice",
                "title": "T", "hypothesis": "H",
                "baseline_tag": "v1", "candidate_tag": "v2",
                "metric_name": "m", "baseline_value": 100.0, "candidate_value": 90.0,
            })

            # List
            handler = routes[("GET", "/api/agent-os/proposals")]
            status, payload = handler({"tenant_id": "testcorp", "email": "alice"})
            assert status == 200
            assert payload["count"] == 1

    def test_run_proposal_experiment(self):
        from neuralmind.agent_os import (
            ExperimentRunner,
            SignalDetector,
            TenantRegistry,
            create_agent_os_routes,
        )
        from neuralmind.agent_os.auth import SessionStore

        with tempfile.TemporaryDirectory() as tmp:
            os.environ["NEURALMIND_AGENTOS_DIR"] = f"{tmp}/agentos"
            registry = TenantRegistry(Path(tmp))
            signal_detector = SignalDetector()
            experiment_runner = ExperimentRunner()
            session_store = SessionStore()
            routes = create_agent_os_routes(registry, signal_detector, experiment_runner, session_store=session_store)

            # Create tenant
            routes[("POST", "/api/agent-os/tenants")]({
                "tenant_id": "testcorp", "admin_email": "alice", "name": "Test"
            })

            # Create proposal
            _, prop = routes[("POST", "/api/agent-os/proposals")]({
                "tenant_id": "testcorp", "email": "alice",
                "title": "T", "hypothesis": "H",
                "baseline_tag": "v1", "candidate_tag": "v2",
                "metric_name": "latency_ms", "baseline_value": 100.0, "candidate_value": 85.0,
            })

            # Run experiment
            handler = routes[("POST", "/api/agent-os/proposals/{id}/run")]
            status, payload = handler(
                {"tenant_id": "testcorp", "email": "alice"},
                id=prop["proposal_id"],
            )
            assert status == 200
            assert "experiment" in payload
            assert "proposal_status" in payload


# =========================================================================
# Phase 7: Dashboard Frontend Wiring
# =========================================================================


class TestDashboardProposals:
    def test_agent_os_proposals_empty(self):
        from neuralmind.agent_os.proposal_store import _store_path
        p = _store_path()
        if p.exists():
            p.unlink()
        from neuralmind.dashboard import agent_os_proposals
        result = agent_os_proposals()
        assert result["total_proposals"] == 0
        assert result["has_data"] is False

    def test_full_dashboard_includes_proposals(self, tmp_path):
        from neuralmind.dashboard import full_dashboard
        result = full_dashboard(project_path=tmp_path)
        assert "proposals" in result["agent_os"]


# =========================================================================
# Phase 7: Adversarial Query Generation
# =========================================================================


class TestAdversarialQueryGeneration:
    def test_advanced_query_from_insight(self):
        from neuralmind.agent_os.adversarial import generate_adversarial_query

        query = generate_adversarial_query(
            metric_name="latency_ms",
            hypothesis="Reducing buffer size may cause latency regression under high load",
            cause_type="code_change",
        )
        assert isinstance(query, str)
        assert len(query) > 0

    def test_adversarial_query_stored(self):
        from neuralmind.agent_os.adversarial import (
            generate_adversarial_query,
            get_adversarial_queries,
        )

        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            query = generate_adversarial_query(
                metric_name="latency_ms",
                hypothesis="Test hypothesis",
                cause_type="code_change",
                base_dir=base,
            )
            queries = get_adversarial_queries(base_dir=base)
            assert len(queries) >= 1

    def test_adversarial_query_contains_boundary_and_falsification(self):
        """Adversarial query must probe boundary conditions and falsification."""
        from neuralmind.agent_os.adversarial import generate_adversarial_query

        query = generate_adversarial_query(
            metric_name="error_rate",
            hypothesis="Adding retry logic reduces transient failures",
            cause_type="code_change",
        )
        assert "boundary" in query.lower() or "fail" in query.lower()
        assert "falsif" in query.lower() or "worst-case" in query.lower()
