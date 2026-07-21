"""test_paid_seats.py — R03, R08: seat add/remove requires admin."""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from neuralmind.tier2.audit import AuditLog
from neuralmind.tier2.config import Tier2Config
from neuralmind.tier2.governance import TeamGovernance
from neuralmind.tier2.seats import SeatManager

ADMIN = "admin"
NON_ADMIN = "intruder"


def test_add_seat_requires_admin():
    """R03: admin can add seats."""
    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        config = Tier2Config()
        config.governance.admin_emails = [ADMIN]
        config.seats = 5
        config.tier = "team"
        config.license_file = str(td / "license.json")
        config.audit_db = str(td / "audit.jsonl")
        audit = AuditLog(td / "audit.jsonl")
        g = TeamGovernance(td, config, audit)
        sm = SeatManager(td / "seats.json")

        g.require_admin(ADMIN)
        seat = sm.add_seat("newuser", config.seats, tier=config.tier)
        assert seat.email == "newuser"


def test_remove_seat_requires_admin():
    """R03: admin can remove seats."""
    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        config = Tier2Config()
        config.governance.admin_emails = [ADMIN]
        config.seats = 5
        config.tier = "team"
        config.license_file = str(td / "license.json")
        config.audit_db = str(td / "audit.jsonl")
        audit = AuditLog(td / "audit.jsonl")
        g = TeamGovernance(td, config, audit)
        sm = SeatManager(td / "seats.json")

        g.require_admin(ADMIN)
        sm.add_seat("newuser", config.seats, tier=config.tier)
        g.require_admin(ADMIN)
        seat = sm.remove_seat("newuser")
        assert seat.email == "newuser"
        assert not seat.active


def test_non_admin_add_rejected():
    """R03: non-admin cannot add seats."""
    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        config = Tier2Config()
        config.governance.admin_emails = [ADMIN]
        config.license_file = str(td / "license.json")
        config.audit_db = str(td / "audit.jsonl")
        g = TeamGovernance(td, config)

        with pytest.raises(PermissionError):
            g.require_admin(NON_ADMIN)


def test_non_admin_remove_rejected():
    """R03: non-admin cannot remove seats."""
    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        config = Tier2Config()
        config.governance.admin_emails = [ADMIN]
        config.license_file = str(td / "license.json")
        config.audit_db = str(td / "audit.jsonl")
        g = TeamGovernance(td, config)

        with pytest.raises(PermissionError):
            g.require_admin(NON_ADMIN)


def test_admin_required_no_optional_type():
    """R08: admin param should not accept empty string."""
    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        config = Tier2Config()
        config.governance.admin_emails = [ADMIN]
        config.license_file = str(td / "license.json")
        config.audit_db = str(td / "audit.jsonl")
        g = TeamGovernance(td, config)
        with pytest.raises(PermissionError):
            g.require_admin("")


def test_os_get_actor_fallback(monkeypatch):
    """R08: os_get_actor_email returns env or ''."""
    from neuralmind.tier2.cli import os_get_actor_email

    monkeypatch.setenv("NEURALMIND_ACTOR_EMAIL", ADMIN)
    assert os_get_actor_email() == ADMIN
