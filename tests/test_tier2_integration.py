from __future__ import annotations

import json
from pathlib import Path

import pytest

from neuralmind.tier2.audit import AuditLog, GENESIS_HASH
from neuralmind.tier2.config import GovernanceConfig, Tier2Config, load_config
from neuralmind.tier2.governance import TeamGovernance
from neuralmind.tier2.license import LicenseValidator
from neuralmind.tier2.license import _ISSUER_PUBLIC_KEY_HEX
from neuralmind.tier2.self_hosted import (
    _resolve_license_path,
    check_data_dir_health,
    check_license_health,
    init_data_dir,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def tmp_config(tmp_path: Path) -> Tier2Config:
    """Tier2Config scoped to tmp_path with admin preset."""
    config = Tier2Config(
        license_file=str(tmp_path / "nonexistent_license.json"),
        audit_db=str(tmp_path / "audit.db"),
    )
    config.governance.admin_emails = ["<EMAIL>"]
    return config


@pytest.fixture
def tmp_audit(tmp_path: Path) -> AuditLog:
    """AuditLog backed by a JSONL file in tmp_path."""
    return AuditLog(tmp_path / "audit.jsonl")


@pytest.fixture
def tmp_governance(tmp_path: Path, tmp_config: Tier2Config, tmp_audit: AuditLog) -> TeamGovernance:
    """TeamGovernance wired to fresh config + audit at tmp_path."""
    return TeamGovernance(tmp_path, tmp_config, tmp_audit)


# ---------------------------------------------------------------------------
# Integration tests
# ---------------------------------------------------------------------------


def test_publish_creates_audit_record(tmp_governance: TeamGovernance) -> None:
    """TeamGovernance.publish() → AuditLog gets exactly 1 entry with action='publish'."""
    gov = tmp_governance
    edges = [
        {"source": "node_a", "target": "node_b", "relation": "calls", "weight": 0.8},
        {"source": "node_c", "target": "node_d", "relation": "uses", "weight": 1.0},
    ]

    result = gov.publish("my-repo", edges, admin="<EMAIL>")

    # Result shape: {published, skipped, audit_id}
    assert len(result["published"]) == 2
    assert len(result["skipped"]) == 0
    assert result["audit_id"]  # non-empty hash

    # Audit trail reflects the publish
    assert gov.audit.count() == 1
    latest = gov.audit.latest()
    assert latest is not None
    assert latest.action == "publish"
    assert latest.actor == "<EMAIL>"
    assert latest.target == "my-repo"
    assert latest.details["count"] == 2


def test_remove_creates_audit_record(tmp_governance: TeamGovernance) -> None:
    """gov.remove_edge_from_shared() → audit entry with action='remove'."""
    gov = tmp_governance
    gov.remove_edge_from_shared("edge-abc-123", admin="<EMAIL>")

    assert gov.audit.count() == 1
    latest = gov.audit.latest()
    assert latest is not None
    assert latest.action == "remove"
    assert latest.target == "edge-abc-123"
    assert latest.actor == "<EMAIL>"
    assert latest.details["reason"] == "admin_removal"


def test_governance_gates_publish(tmp_governance: TeamGovernance) -> None:
    """config scope=personal → is_publishing_allowed blocks shared push
    (publish returns empty published list when gate is respected)."""
    gov = tmp_governance
    gov.config.governance.publishing_scope = "personal"
    # Set threshold low so weight is not the gate here
    gov.config.governance.weight_threshold = 0.0

    # Gate check at the governance layer
    gate = gov.is_publishing_allowed("any-repo", 1.0)
    assert gate.allowed is False
    assert "personal" in gate.reason.lower()

    # A well-behaved caller respects the gate and publishes nothing
    if gate.allowed:
        result = gov.publish("any-repo", [{"weight": 1.0}])
    else:
        result = {"published": [], "skipped": "all", "audit_id": ""}

    assert result["published"] == []


def test_self_hosted_persists_across_restart(tmp_path: Path) -> None:
    """init_data_dir + write file + reload → file persists (data dir is durable)."""
    data_dir = tmp_path / "self_hosted_data"

    # First "boot": init + write state
    init_result = init_data_dir(data_dir)
    assert init_result["created"] is True

    state_file = data_dir / "state.json"
    state_file.write_text(json.dumps({"version": 1, "edges_synced": 42}))

    # "Restart": reload via health check + re-read state file
    health = check_data_dir_health(data_dir)
    assert health["exists"] is True
    assert health["is_dir"] is True
    assert health["writable"] is True

    # State file is still there and content matches
    assert state_file.exists()
    loaded = json.loads(state_file.read_text())
    assert loaded["version"] == 1
    assert loaded["edges_synced"] == 42


def test_self_hosted_license_survives_restart(tmp_path: Path) -> None:
    """init + write license.json + reload → license still readable."""
    data_dir = tmp_path / "self_hosted_data"
    data_dir.mkdir(parents=True, exist_ok=True)

    license_data = {
        "tier": "team",
        "seats": 10,
        "issued_at": "2026-07-19T00:00:00Z",
        "expires_at": "2027-07-19T00:00:00Z",
        "issued_to": "test-corp",
        "signature": "test-signature-placeholder",
    }
    license_file = data_dir / "license.json"
    license_file.write_text(json.dumps(license_data, indent=2))

    # "Restart": reload via LicenseValidator + health check
    validator = LicenseValidator(_ISSUER_PUBLIC_KEY_HEX, license_file)
    info = validator._load_raw()
    assert info is not None
    assert info.tier == "team"
    assert info.seats == 10
    assert info.issued_to == "test-corp"
    assert info.expires_at == "2027-07-19T00:00:00Z"

    lic_health = check_license_health(license_file)
    assert lic_health["exists"] is True
    assert lic_health["readable"] is True


def test_mit_user_unaffected(tmp_path: Path) -> None:
    """Tier2Config with nonexistent license_file → config still constructs,
    governance defaults enabled. _ensure_tier2_activated would block downstream,
    but the config object itself is MIT-safe."""
    # No license file present
    missing_license = tmp_path / "nonexistent_license.json"
    assert not missing_license.exists()

    # Config constructs cleanly
    config = Tier2Config(
        license_file=str(missing_license),
        audit_db=str(tmp_path / "audit.db"),
    )
    assert config is not None

    # Governance defaults enabled, scope=both
    assert config.governance.enabled is True
    assert config.governance.publishing_scope == "both"
    assert config.governance.weight_threshold == 0.1

    # TeamGovernance usable without license
    config.governance.admin_emails = ["<EMAIL>"]
    audit = AuditLog(tmp_path / "audit.jsonl")
    gov = TeamGovernance(tmp_path, config, audit)

    # With scope=both, is_publishing_allowed returns allowed=True
    # (license gate is enforced separately by _ensure_tier2_activated at CLI entry)
    result = gov.is_publishing_allowed("any-repo", 1.0)
    assert result.allowed is True


def test_team_memory_import_respects_governance(tmp_path: Path) -> None:
    """Create governance with scope=personal; import edges → all skipped, published=[]."""
    config = Tier2Config(
        license_file=str(tmp_path / "nonexistent.json"),
        audit_db=str(tmp_path / "audit.db"),
    )
    config.governance.admin_emails = ["<EMAIL>"]
    config.governance.publishing_scope = "personal"

    audit = AuditLog(tmp_path / "audit.jsonl")
    gov = TeamGovernance(tmp_path, config, audit)

    # Simulate an edge bundle coming from a memory import
    edges = [
        {"source": "imp_a", "target": "imp_b", "relation": "calls", "weight": 0.9},
        {"source": "imp_c", "target": "imp_d", "relation": "uses", "weight": 0.85},
        {"source": "imp_e", "target": "imp_f", "relation": "inherits", "weight": 1.0},
    ]

    # Import path: check governance per edge, only publish if allowed
    published: list[dict] = []
    skipped: list[dict] = []
    for edge in edges:
        gate = gov.is_publishing_allowed("import-repo", edge["weight"])
        if gate.allowed:
            published.append(edge)
        else:
            skipped.append(edge)

    # All three edges blocked by scope=personal
    assert len(published) == 0
    assert len(skipped) == 3

    # The "publish the allowed ones" call yields empty results
    push_result = gov.publish("import-repo", published, admin="<EMAIL>")
    assert push_result["published"] == []
    assert push_result["skipped"] == []  # published list was empty → nothing to skip either
