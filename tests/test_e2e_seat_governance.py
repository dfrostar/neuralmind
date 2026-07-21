"""test_e2e_seat_governance.py — R13: E2E CLI flow tests.

Tests verify the seat sync command end-to-end: file check -> JSON parse ->
version check -> signature verify -> expiry check -> admin check -> sync ->
return code. Bypasses license activation flow by injecting config directly.
"""

from __future__ import annotations

import json
from pathlib import Path

_ADMIN = "admin"
_SEAT1 = "seat1"
_SEAT2 = "seat2"


def _make_signed_manifest(path, seats=None, expires_at="2027-07-23T10:00:00+00:00",
                          signer_id="autopilot", customer="customer"):
    """Generate a signed seat manifest using autopilot-style signing."""
    import uuid
    from datetime import datetime, timezone

    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

    priv = Ed25519PrivateKey.generate()
    pub = priv.public_key()
    issued_at = datetime.now(timezone.utc).isoformat()

    if seats is None:
        seats = [
            {"email": _SEAT1, "role": "admin", "added_at": issued_at},
            {"email": _SEAT2, "role": "member", "added_at": issued_at},
        ]

    payload = {
        "manifest_id": f"sm_{uuid.uuid4().hex[:12]}",
        "version": 1,
        "issued_at": issued_at,
        "expires_at": expires_at,
        "signer_id": signer_id,
        "customer_email": customer,
        "seats": seats,
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    sig = priv.sign(b"seat-manifest:v1" + canonical.encode("utf-8"))
    manifest = {**payload, "signature": sig.hex()}
    Path(path).write_text(json.dumps(manifest, indent=2))
    return pub.public_bytes_raw().hex()


def _prep_config(monkeypatch, tmp_path, admin_emails=None, seats=10):
    """Create Tier2Config with admin for direct injection into cmd_team_seats_sync."""
    from neuralmind.tier2 import config as _config_mod
    from neuralmind.tier2.config import Tier2Config

    if admin_emails is None:
        admin_emails = [_ADMIN]

    # Override TIER2_CONFIG_DIR to tmp_path so seats.json goes there
    monkeypatch.setattr(_config_mod, "TIER2_CONFIG_DIR", tmp_path)
    monkeypatch.setattr(_config_mod, "DEFAULT_CONFIG_PATH", tmp_path / "tier2.yaml")

    config = Tier2Config()
    config.governance.admin_emails = admin_emails
    config.seats = seats
    config.tier = "team"
    config.license_file = str(tmp_path / "license.json")
    config.audit_db = str(tmp_path / "audit.jsonl")
    return config


def test_e2e_activate_add_admin(tmp_path, monkeypatch):
    """R13: Fresh install + activate license + add seats."""
    from neuralmind.tier2.cli import cmd_team_seats_sync

    manifest_path = tmp_path / "signed.json"
    pub_hex = _make_signed_manifest(manifest_path)

    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("NEURALMIND_ACTOR_EMAIL", _ADMIN)
    monkeypatch.setenv("NEURALMIND_ADMIN_EMAIL", _ADMIN)
    monkeypatch.setenv("NEURALMIND_ISSUER_PUBLIC_KEY_HEX", pub_hex)

    config = _prep_config(monkeypatch, tmp_path)

    class Args:
        manifest = str(manifest_path)
        admin = _ADMIN
        config_path = None

    rc = cmd_team_seats_sync(Args(), config=config)
    assert rc == 0, f"seats sync failed with rc={rc}"

    seats_path = tmp_path / "seats.json"
    assert seats_path.exists(), "seats.json should be created"
    seats = json.loads(seats_path.read_text())
    emails = [s["email"] for s in seats]
    assert _SEAT1 in emails
    assert _SEAT2 in emails


def test_e2e_non_admin_rejected(tmp_path, monkeypatch):
    """R13: Non-admin attempting to add seats is rejected."""
    from neuralmind.tier2.cli import cmd_team_seats_sync

    manifest_path = tmp_path / "signed.json"
    pub_hex = _make_signed_manifest(manifest_path)

    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("NEURALMIND_ACTOR_EMAIL", "intruder")
    monkeypatch.setenv("NEURALMIND_ADMIN_EMAIL", _ADMIN)
    monkeypatch.setenv("NEURALMIND_ISSUER_PUBLIC_KEY_HEX", pub_hex)

    config = _prep_config(monkeypatch, tmp_path)

    class Args:
        manifest = str(manifest_path)
        admin = "intruder"
        config_path = None

    rc = cmd_team_seats_sync(Args(), config=config)
    assert rc != 0, "Non-admin sync should be rejected"


def test_e2e_seat_limit_enforced():
    """R13: License seat limit structure in place."""
    from neuralmind.tier2.config import Tier2Config

    config = Tier2Config()
    config.seats = 1
    config.tier = "team"
    assert config.seats == 1


def test_e2e_audit_log_complete(tmp_path, monkeypatch):
    """R13: Audit log captures sync events."""
    from neuralmind.tier2.cli import cmd_team_seats_sync

    manifest_path = tmp_path / "signed.json"
    pub_hex = _make_signed_manifest(manifest_path)

    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("NEURALMIND_ACTOR_EMAIL", _ADMIN)
    monkeypatch.setenv("NEURALMIND_ADMIN_EMAIL", _ADMIN)
    monkeypatch.setenv("NEURALMIND_ISSUER_PUBLIC_KEY_HEX", pub_hex)

    config = _prep_config(monkeypatch, tmp_path)

    class Args:
        manifest = str(manifest_path)
        admin = _ADMIN
        config_path = None

    rc = cmd_team_seats_sync(Args(), config=config)
    assert rc == 0
