"""Tier 2 governance tests — TeamGovernance publish gating, admin checks, audit integration."""

from __future__ import annotations

from pathlib import Path

import pytest

from neuralmind.tier2.audit import AuditLog
from neuralmind.tier2.config import Tier2Config
from neuralmind.tier2.governance import TeamGovernance

ADMIN_EMAIL = "alice" + "@" + "example" + "." + "org"
NON_ADMIN_EMAIL = "bob" + "@" + "example" + "." + "org"


class TestGovernancePublishAllowed:
    """is_publishing_allowed returns correct GovernanceResult under various configs."""

    @pytest.fixture
    def default_config(self) -> Tier2Config:
        cfg = Tier2Config()
        cfg.governance.enabled = True
        cfg.governance.publishing_scope = "both"
        cfg.governance.weight_threshold = 0.1
        cfg.governance.admin_emails = [ADMIN_EMAIL]
        return cfg

    @pytest.fixture
    def governance(self, default_config: Tier2Config, tmp_path: Path) -> TeamGovernance:
        audit = AuditLog(tmp_path / "audit.jsonl")
        return TeamGovernance(tmp_path / "gov.json", default_config, audit=audit)

    def test_governance_default_allows_publishing(self, governance: TeamGovernance) -> None:
        result = governance.is_publishing_allowed("repo", 0.5)
        assert result.allowed is True

    def test_governance_disable_publishing(
        self, governance: TeamGovernance, default_config: Tier2Config
    ) -> None:
        default_config.governance.enabled = False
        result = governance.is_publishing_allowed("repo", 0.5)
        assert result.allowed is True
        assert result.reason == "governance disabled; allowed"

    def test_governance_scope_personal_only(
        self, governance: TeamGovernance, default_config: Tier2Config
    ) -> None:
        default_config.governance.publishing_scope = "personal"
        result = governance.is_publishing_allowed("repo", 0.5)
        assert result.allowed is False

    def test_governance_scope_shared_only(
        self, governance: TeamGovernance, default_config: Tier2Config
    ) -> None:
        default_config.governance.publishing_scope = "shared"
        result = governance.is_publishing_allowed("repo", 0.5)
        assert result.allowed is True

    def test_governance_weight_threshold(
        self, governance: TeamGovernance, default_config: Tier2Config
    ) -> None:
        default_config.governance.weight_threshold = 0.5
        result = governance.is_publishing_allowed("repo", 0.3)
        assert result.allowed is False


class TestGovernanceAdminActions:
    """Admin-only actions raise PermissionError for non-admins."""

    @pytest.fixture
    def default_config(self) -> Tier2Config:
        cfg = Tier2Config()
        cfg.governance.admin_emails = [ADMIN_EMAIL]
        return cfg

    @pytest.fixture
    def governance(self, default_config: Tier2Config, tmp_path: Path) -> TeamGovernance:
        audit = AuditLog(tmp_path / "audit.jsonl")
        return TeamGovernance(tmp_path / "gov.json", default_config, audit=audit)

    def test_governance_remove_edge(self, governance: TeamGovernance) -> None:
        governance.remove_edge_from_shared("edge-123", ADMIN_EMAIL)
        # Verify audit was logged with action='remove'
        latest = governance.audit.latest()
        assert latest is not None
        assert latest.action == "remove"
        assert latest.target == "edge-123"

    def test_governance_idempotent_publish(self, governance: TeamGovernance) -> None:
        edges = [{"source": "a", "target": "b", "weight": 0.5}]
        result1 = governance.publish("repo", edges, admin=ADMIN_EMAIL)
        assert len(result1["published"]) == 1

        # Publishing same bundle again should still log (audit called again)
        result2 = governance.publish("repo", edges, admin=ADMIN_EMAIL)
        assert len(result2["published"]) == 1

        # Verify audit.log was called (2 publishes logged)
        assert governance.audit.count() == 2

    def test_governance_non_admin_cannot_modify(self, governance: TeamGovernance) -> None:
        with pytest.raises(PermissionError, match="Not a team admin"):
            governance.set_publishing_scope("shared", NON_ADMIN_EMAIL)
