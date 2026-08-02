"""Tests for the Agent OS: tenant registry, governance, signals, experiments."""

from __future__ import annotations

import pytest

from neuralmind.agent_os import (
    AgentOSGovernance,
    ExperimentRunner,
    ExperimentStatus,
    Permission,
    SignalDetector,
    Tenant,
    TenantConflictError,
    TenantRegistry,
    validate_tenant_id,
)
from neuralmind.agent_os.governance import check_permission, role_has_permission
from neuralmind.agent_os.tenant import RoleAssignment

# ---------------------------------------------------------------------------
# Tenant
# ---------------------------------------------------------------------------


class TestTenant:
    def test_create_basic(self):
        t = Tenant(tenant_id="acme", name="Acme Corp")
        assert t.tenant_id == "acme"
        assert t.name == "Acme Corp"
        assert t.tier == "free"
        assert t.projects == []
        assert t.rbac == []

    def test_is_admin(self):
        t = Tenant(
            tenant_id="acme",
            name="Acme",
            rbac=[RoleAssignment(email="alice@example.com", role="admin")],
        )
        assert t.is_admin("alice@example.com") is True
        assert t.is_admin("bob@example.com") is False
        assert t.is_admin("") is False
        assert t.is_admin(None) is False

    def test_is_operator(self):
        t = Tenant(
            tenant_id="acme",
            name="Acme",
            rbac=[
                RoleAssignment(email="alice@example.com", role="admin"),
                RoleAssignment(email="bob@example.com", role="operator"),
                RoleAssignment(email="carol@example.com", role="viewer"),
            ],
        )
        assert t.is_operator("alice@example.com") is True
        assert t.is_operator("bob@example.com") is True
        assert t.is_operator("carol@example.com") is False

    def test_has_access(self):
        t = Tenant(
            tenant_id="acme",
            name="Acme",
            rbac=[RoleAssignment(email="alice@example.com", role="admin")],
        )
        assert t.has_access("alice@example.com") is True
        assert t.has_access("eve@example.com") is False

    def test_to_dict_roundtrip(self):
        t = Tenant(
            tenant_id="acme",
            name="Acme Corp",
            tier="team",
            projects=["/tmp/proj1"],
            rbac=[RoleAssignment(email="alice@example.com", role="admin")],
        )
        data = t.to_dict()
        t2 = Tenant.from_dict(data)
        assert t2.tenant_id == t.tenant_id
        assert t2.name == t.name
        assert t2.tier == t.tier
        assert t2.projects == t.projects
        assert len(t2.rbac) == 1
        assert t2.rbac[0].email == "alice@example.com"

    def test_from_dict_with_rbac_dicts(self):
        """from_dict handles rbac as list of dicts (from JSON)."""
        data = {
            "tenant_id": "acme",
            "name": "Acme",
            "rbac": [{"email": "alice@example.com", "role": "admin"}],
        }
        t = Tenant.from_dict(data)
        assert t.rbac[0].email == "alice@example.com"
        assert t.rbac[0].role == "admin"


class TestTenantIdValidation:
    def test_valid_ids(self):
        assert validate_tenant_id("acme") == "acme"
        assert validate_tenant_id("acme-corp") == "acme-corp"
        assert validate_tenant_id("acme123") == "acme123"
        assert validate_tenant_id("a" * 64) == "a" * 64

    def test_invalid_ids(self):
        from neuralmind.agent_os.tenant import InvalidTenantIdError

        with pytest.raises(InvalidTenantIdError):
            validate_tenant_id("")
        with pytest.raises(InvalidTenantIdError):
            validate_tenant_id("Acme")  # uppercase
        with pytest.raises(InvalidTenantIdError):
            validate_tenant_id("123acme")  # starts with digit
        with pytest.raises(InvalidTenantIdError):
            validate_tenant_id("acme_corp")  # underscore
        with pytest.raises(InvalidTenantIdError):
            validate_tenant_id("a" * 65)  # too long


# ---------------------------------------------------------------------------
# TenantRegistry
# ---------------------------------------------------------------------------


class TestTenantRegistry:
    def test_create_and_get(self, tmp_path):
        reg = TenantRegistry(tmp_path)
        t = reg.create_tenant("acme", "Acme Corp", admin_email="alice@example.com")
        assert t.tenant_id == "acme"
        assert t.is_admin("alice@example.com")

        fetched = reg.get_tenant("acme")
        assert fetched is not None
        assert fetched.tenant_id == "acme"

    def test_get_nonexistent_returns_none(self, tmp_path):
        reg = TenantRegistry(tmp_path)
        assert reg.get_tenant("ghost") is None

    def test_duplicate_tenant_id_raises(self, tmp_path):
        reg = TenantRegistry(tmp_path)
        reg.create_tenant("acme", "Acme", admin_email="alice@example.com")
        with pytest.raises(TenantConflictError):
            reg.create_tenant("acme", "Acme 2", admin_email="bob@example.com")

    def test_project_conflict(self, tmp_path):
        reg = TenantRegistry(tmp_path)
        reg.create_tenant("acme", "Acme", admin_email="alice@example.com")
        reg.add_project("acme", "/tmp/proj1", "alice@example.com")

        reg.create_tenant("other", "Other", admin_email="bob@example.com")
        with pytest.raises(TenantConflictError):
            reg.add_project("other", "/tmp/proj1", "bob@example.com")

    def test_get_tenant_by_project(self, tmp_path):
        reg = TenantRegistry(tmp_path)
        reg.create_tenant("acme", "Acme", admin_email="alice@example.com")
        reg.add_project("acme", "/tmp/proj1", "alice@example.com")

        t = reg.get_tenant_by_project("/tmp/proj1")
        assert t is not None
        assert t.tenant_id == "acme"

    def test_list_tenants(self, tmp_path):
        reg = TenantRegistry(tmp_path)
        reg.create_tenant("acme", "Acme", admin_email="alice@example.com")
        reg.create_tenant("zebra", "Zebra Inc", admin_email="bob@example.com")
        tenants = reg.list_tenants()
        assert len(tenants) == 2
        # Sorted by name
        assert tenants[0].tenant_id == "acme"
        assert tenants[1].tenant_id == "zebra"

    def test_add_role(self, tmp_path):
        reg = TenantRegistry(tmp_path)
        reg.create_tenant("acme", "Acme", admin_email="alice@example.com")
        reg.add_role("acme", "bob@example.com", "operator", "alice@example.com")

        t = reg.get_tenant("acme")
        assert t is not None
        assert t.is_operator("bob@example.com")

    def test_add_role_non_admin_raises(self, tmp_path):
        reg = TenantRegistry(tmp_path)
        reg.create_tenant("acme", "Acme", admin_email="alice@example.com")
        reg.add_role("acme", "bob@example.com", "operator", "alice@example.com")

        with pytest.raises(PermissionError):
            reg.add_role("acme", "eve@example.com", "admin", "bob@example.com")

    def test_remove_project(self, tmp_path):
        reg = TenantRegistry(tmp_path)
        reg.create_tenant("acme", "Acme", admin_email="alice@example.com")
        reg.add_project("acme", "/tmp/proj1", "alice@example.com")
        reg.remove_project("acme", "/tmp/proj1", "alice@example.com")

        assert reg.get_tenant_by_project("/tmp/proj1") is None

    def test_delete_tenant(self, tmp_path):
        reg = TenantRegistry(tmp_path)
        reg.create_tenant("acme", "Acme", admin_email="alice@example.com")
        reg.delete_tenant("acme", "alice@example.com")
        assert reg.get_tenant("acme") is None

    def test_delete_tenant_non_admin_raises(self, tmp_path):
        reg = TenantRegistry(tmp_path)
        reg.create_tenant("acme", "Acme", admin_email="alice@example.com")
        with pytest.raises(PermissionError):
            reg.delete_tenant("acme", "eve@example.com")

    def test_persistence(self, tmp_path):
        """Tenants persist across registry instances."""
        reg1 = TenantRegistry(tmp_path)
        reg1.create_tenant("acme", "Acme", admin_email="alice@example.com")

        reg2 = TenantRegistry(tmp_path)
        t = reg2.get_tenant("acme")
        assert t is not None
        assert t.name == "Acme"


# ---------------------------------------------------------------------------
# Governance
# ---------------------------------------------------------------------------


class TestRolePermissions:
    def test_admin_has_all_permissions(self):
        for perm in Permission:
            assert role_has_permission("admin", perm) is True

    def test_operator_permissions(self):
        assert role_has_permission("operator", Permission.MANAGE_PROJECTS) is True
        assert role_has_permission("operator", Permission.VIEW_SIGNALS) is True
        assert role_has_permission("operator", Permission.RUN_EXPERIMENTS) is True
        assert role_has_permission("operator", Permission.DELETE_TENANT) is False
        assert role_has_permission("operator", Permission.MANAGE_RBAC) is False

    def test_viewer_permissions(self):
        assert role_has_permission("viewer", Permission.VIEW_PROJECTS) is True
        assert role_has_permission("viewer", Permission.VIEW_SIGNALS) is True
        assert role_has_permission("viewer", Permission.MANAGE_PROJECTS) is False
        assert role_has_permission("viewer", Permission.RUN_EXPERIMENTS) is False

    def test_unknown_role_defaults_to_viewer(self):
        assert role_has_permission("superadmin", Permission.VIEW_PROJECTS) is True
        assert role_has_permission("superadmin", Permission.DELETE_TENANT) is False


class TestCheckPermission:
    def test_check_permission(self):
        t = Tenant(
            tenant_id="acme",
            name="Acme",
            rbac=[RoleAssignment(email="alice@example.com", role="admin")],
        )
        assert check_permission(t, "alice@example.com", Permission.DELETE_TENANT) is True
        assert check_permission(t, "alice@example.com", Permission.VIEW_PROJECTS) is True

    def test_check_permission_denied(self):
        t = Tenant(
            tenant_id="acme",
            name="Acme",
            rbac=[RoleAssignment(email="carol@example.com", role="viewer")],
        )
        assert check_permission(t, "carol@example.com", Permission.DELETE_TENANT) is False


class TestAgentOSGovernance:
    def test_enforce_grants(self, tmp_path):
        reg = TenantRegistry(tmp_path)
        reg.create_tenant("acme", "Acme", admin_email="alice@example.com")
        gov = AgentOSGovernance(reg)

        result = gov.enforce("acme", "alice@example.com", Permission.DELETE_TENANT)
        assert result.allowed is True

    def test_enforce_denies(self, tmp_path):
        reg = TenantRegistry(tmp_path)
        reg.create_tenant("acme", "Acme", admin_email="alice@example.com")
        reg.add_role("acme", "carol@example.com", "viewer", "alice@example.com")
        gov = AgentOSGovernance(reg)

        result = gov.enforce("acme", "carol@example.com", Permission.DELETE_TENANT)
        assert result.allowed is False

    def test_list_accessible_tenants(self, tmp_path):
        reg = TenantRegistry(tmp_path)
        reg.create_tenant("acme", "Acme", admin_email="alice@example.com")
        reg.create_tenant("other", "Other", admin_email="bob@example.com")
        gov = AgentOSGovernance(reg)

        tenants = gov.list_accessible_tenants("alice@example.com")
        assert len(tenants) == 1
        assert tenants[0].tenant_id == "acme"

    def test_can_access_project(self, tmp_path):
        reg = TenantRegistry(tmp_path)
        reg.create_tenant("acme", "Acme", admin_email="alice@example.com")
        reg.add_project("acme", "/tmp/proj1", "alice@example.com")
        gov = AgentOSGovernance(reg)

        assert gov.can_access_project("alice@example.com", "/tmp/proj1") is True
        assert gov.can_access_project("eve@example.com", "/tmp/proj1") is False


# ---------------------------------------------------------------------------
# Signals
# ---------------------------------------------------------------------------


class TestSignalDetector:
    def test_no_signal_on_stable_data(self):
        sd = SignalDetector()
        for _i in range(100):
            result = sd.update("latency", 100.0)
        assert result is None

    def test_signal_on_persistent_shift(self):
        sd = SignalDetector(lambda_threshold=2.0)
        # Warm up with baseline
        for _ in range(50):
            sd.update("latency", 100.0)
        # Shift up
        signal = None
        for _ in range(50):
            result = sd.update("latency", 200.0)
            if result is not None:
                signal = result
                break
        assert signal is not None
        assert signal.metric_name == "latency"
        assert signal.value == 200.0

    def test_severity_levels(self):
        sd = SignalDetector(lambda_threshold=1.0)
        # Warm up
        for _ in range(100):
            sd.update("m", 100.0)
        # Small shift
        signal = None
        for _ in range(100):
            result = sd.update("m", 110.0)
            if result is not None:
                signal = result
                break
        assert signal is not None

    def test_cooldown_prevents_spam(self):
        sd = SignalDetector(lambda_threshold=1.0, cooldown_seconds=10.0)
        # Warm up
        for _ in range(100):
            sd.update("m", 100.0)
        # Trigger signal
        signal1 = None
        for _ in range(100):
            result = sd.update("m", 300.0)
            if result is not None:
                signal1 = result
                break
        assert signal1 is not None
        # Immediate second signal should be suppressed by cooldown
        signal2 = sd.update("m", 300.0)
        assert signal2 is None

    def test_update_batch(self):
        sd = SignalDetector()
        signals = sd.update_batch({"a": 1.0, "b": 2.0, "c": 3.0})
        assert isinstance(signals, list)

    def test_get_stats(self):
        sd = SignalDetector()
        for _ in range(10):
            sd.update("m", 5.0)
        stats = sd.get_stats("m")
        assert stats is not None
        assert stats["count"] == 10
        assert stats["running_mean"] == 5.0

    def test_reset(self):
        sd = SignalDetector()
        sd.update("a", 1.0)
        sd.update("b", 2.0)
        assert len(sd.list_metrics()) == 2
        sd.reset("a")
        assert len(sd.list_metrics()) == 1
        sd.reset()
        assert len(sd.list_metrics()) == 0


# ---------------------------------------------------------------------------
# Experiments
# ---------------------------------------------------------------------------


class TestExperimentRunner:
    def test_promote_on_improvement(self):
        runner = ExperimentRunner(promote_threshold_pct=5.0)
        result = runner.run(
            proposal_id="p1",
            metric_name="latency_ms",
            baseline_value=100.0,
            candidate_value=90.0,  # 10% improvement (lower is better)
        )
        assert result.verdict == ExperimentStatus.PROMOTED
        assert result.delta == 0.10  # positive = improvement after normalization

    def test_rollback_on_regression(self):
        runner = ExperimentRunner(rollback_threshold_pct=-3.0)
        result = runner.run(
            proposal_id="p1",
            metric_name="latency_ms",
            baseline_value=100.0,
            candidate_value=110.0,  # 10% regression (lower-is-better, so higher = worse)
        )
        assert result.verdict == ExperimentStatus.ROLLED_BACK
        assert result.delta == -0.10  # negative = worse after normalization

    def test_reject_when_inconclusive(self):
        runner = ExperimentRunner(promote_threshold_pct=10.0)
        result = runner.run(
            proposal_id="p1",
            metric_name="latency_ms",
            baseline_value=100.0,
            candidate_value=95.0,  # 5% improvement, below threshold
        )
        assert result.verdict == ExperimentStatus.REJECTED

    def test_zero_baseline_handled(self):
        runner = ExperimentRunner()
        result = runner.run(
            proposal_id="p1",
            metric_name="m",
            baseline_value=0.0,
            candidate_value=1.0,
        )
        # Should not crash
        # Default is lower_is_better: candidate > baseline is a regression → negative delta.
        assert result.delta == -1.0

    def test_zero_baseline_higher_is_better(self):
        """Zero-baseline branch must honor higher_is_better directionality."""
        runner = ExperimentRunner()
        result = runner.run(
            proposal_id="p1",
            metric_name="m",
            baseline_value=0.0,
            candidate_value=10.0,
            higher_is_better=True,  # throughput: candidate > baseline is an improvement
        )
        assert result.delta == 1.0
        assert result.verdict == ExperimentStatus.PROMOTED

    def test_history(self):
        runner = ExperimentRunner()
        runner.run("p1", "m", 100.0, 90.0)
        runner.run("p2", "m", 100.0, 80.0)
        history = runner.get_history()
        assert len(history) == 2
        # Newest first
        assert history[0].proposal_id == "p2"

    def test_clear_history(self):
        runner = ExperimentRunner()
        runner.run("p1", "m", 100.0, 90.0)
        runner.clear_history()
        assert len(runner.get_history()) == 0

    def test_p_value_none_with_few_samples(self):
        """p-value is None when <2 historical samples."""
        runner = ExperimentRunner()
        result = runner.run("p1", "m", 100.0, 90.0)
        assert result.p_value is None

    def test_p_value_computed_with_history(self):
        """p-value is computed when >=2 historical samples exist."""
        runner = ExperimentRunner()
        runner.run("p1", "m", 100.0, 90.0)
        runner.run("p2", "m", 100.0, 80.0)
        result = runner.run("p3", "m", 100.0, 95.0)
        assert result.p_value is not None
        assert 0.0 <= result.p_value <= 1.0


# ---------------------------------------------------------------------------
# Integration: signal → experiment
# ---------------------------------------------------------------------------


class TestSignalExperimentIntegration:
    def test_anomaly_triggers_experiment(self):
        """A signal anomaly can trigger an experiment."""
        sd = SignalDetector(lambda_threshold=1.0)
        runner = ExperimentRunner(promote_threshold_pct=5.0)

        # Warm up
        for _ in range(100):
            sd.update("latency_ms", 100.0)

        # Shift and detect
        signal = None
        for _ in range(100):
            result = sd.update("latency_ms", 200.0)
            if result is not None:
                signal = result
                break

        assert signal is not None

        # Run experiment comparing baseline to candidate
        result = runner.run(
            proposal_id=f"exp_fix_{signal.signal_id}",
            metric_name="latency_ms",
            baseline_value=signal.value,
            candidate_value=signal.baseline,  # "fix" restores baseline
        )
        # The "fix" is a 50% improvement → promoted
        assert result.verdict == ExperimentStatus.PROMOTED
