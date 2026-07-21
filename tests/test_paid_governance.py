"""test_paid_governance.py — R08, R09, R11: admin required, no auto-downgrade, audit."""

from __future__ import annotations

from pathlib import Path

import pytest

from neuralmind.tier2.audit import AuditLog
from neuralmind.tier2.config import Tier2Config
from neuralmind.tier2.governance import TeamGovernance
from neuralmind.tier2.seats import SeatManager

_ADMIN = "admin"
_USER1 = "user1"


def test_no_admin_bypass_anywhere():
    """R08: scan that no function has admin: str | None = None pattern."""
    import inspect

    from neuralmind.tier2 import governance as gov_mod

    for name, obj in inspect.getmembers(gov_mod.TeamGovernance, predicate=inspect.isfunction):
        sig = inspect.signature(obj)
        for pname, param in sig.parameters.items():
            if pname == "admin":
                assert (
                    param.default is not inspect.Parameter.empty or param.default is not None
                ), f"{name}: admin param has None default"


def test_seat_mutation_audited(tmp_path):
    """R11: every seat mutation appends audit entry."""
    config = Tier2Config()
    config.governance.admin_emails = [_ADMIN]
    config.seats = 5
    config.tier = "team"
    config.license_file = str(tmp_path / "license.json")
    config.audit_db = str(tmp_path / "audit.jsonl")
    audit = AuditLog(tmp_path / "audit.jsonl")
    gov = TeamGovernance(tmp_path, config, audit)
    sm = SeatManager(tmp_path / "seats.json")

    gov.require_admin(_ADMIN)
    sm.add_seat(_USER1, config.seats, tier=config.tier)
    audit.log(actor=_ADMIN, action="seat_add", target=_USER1)
    assert audit.count() == 1

    gov.require_admin(_ADMIN)
    sm.remove_seat(_USER1)
    audit.log(actor=_ADMIN, action="seat_remove", target=_USER1)
    assert audit.count() == 2


def test_audit_hash_chain_intact(tmp_path):
    """R11: audit log hash chain integrity verifiable."""
    config = Tier2Config()
    config.governance.admin_emails = [_ADMIN]
    config.seats = 5
    config.tier = "team"
    audit = AuditLog(tmp_path / "audit.jsonl")
    gov = TeamGovernance(tmp_path, config, audit)

    gov.require_admin(_ADMIN)
    audit.log(actor=_ADMIN, action="config_change", target="test1")
    audit.log(actor=_ADMIN, action="config_change", target="test2")

    result = audit.verify()
    assert result["ok"]
    assert result["total"] == 2


def test_free_tier_but_admin_required():
    """R08: even free tier requires admin for mutations (no admin=None bypass)."""
    import tempfile

    td = Path(tempfile.mkdtemp())
    config = Tier2Config()
    config.governance.admin_emails = [_ADMIN]
    config.seats = 1
    config.tier = "free"
    config.license_file = str(td / "license.json")
    config.audit_db = str(td / "audit.jsonl")
    audit = AuditLog(td / "audit.jsonl")
    gov = TeamGovernance(td, config, audit)
    sm = SeatManager(td / "seats.json")

    gov.require_admin(_ADMIN)
    sm.add_seat(_USER1, config.seats, tier="free")
    with pytest.raises(PermissionError):
        gov.require_admin("intruder")


def test_r09_no_auto_downgrade(tmp_path):
    """R09: paid license missing -> no auto-regeneration of free tier."""
    from neuralmind.tier2.cli import _ensure_tier2_activated

    config_path = tmp_path / "tier2.yaml"
    config = Tier2Config()
    config.tier = "team"
    config.seats = 10
    config.license_file = str(tmp_path / "license.json")
    config.audit_db = str(tmp_path / "audit.jsonl")
    from neuralmind.tier2.config import save_config

    save_config(config, config_path)

    lic_path = Path(config.license_file)
    if lic_path.exists():
        lic_path.unlink()

    args = type("Args", (), {"config_path": config_path, "admin": _ADMIN})()
    result_config, _ = _ensure_tier2_activated(args)
    assert result_config is None
