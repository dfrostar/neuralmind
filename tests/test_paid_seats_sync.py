"""test_paid_seats_sync.py — R02: sync seats from signed manifest."""

from __future__ import annotations

import json

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from neuralmind.tier2.seats import sync_seats, verify_manifest_signature

_ADMIN = "admin"
_SEAT1 = "seat1"
_SEAT2 = "seat2"


def _issue_manifest(seats, private_key_hex, expires_at="2027-07-23T10:00:00+00:00"):
    """Issue a valid seat manifest (signing via autopilot-style canonical JSON)."""
    import uuid
    from datetime import datetime, timezone

    issued_at = datetime.now(timezone.utc).isoformat()
    priv_key = Ed25519PrivateKey.from_private_bytes(bytes.fromhex(private_key_hex))

    payload = {
        "manifest_id": f"sm_{uuid.uuid4().hex[:12]}",
        "version": 1,
        "issued_at": issued_at,
        "expires_at": expires_at,
        "signer_id": "autopilot",
        "customer_email": "customer",
        "seats": [
            {"email": s["email"].strip().lower(), "role": s.get("role", "member"), "added_at": issued_at}
            for s in seats
        ],
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    sig = priv_key.sign(b"seat-manifest:v1" + canonical.encode("utf-8"))
    return {**payload, "signature": sig.hex()}


@pytest.fixture
def keypair():
    priv = Ed25519PrivateKey.generate()
    pub = priv.public_key()
    return {
        "private_key_hex": priv.private_bytes_raw().hex(),
        "public_key_hex": pub.public_bytes_raw().hex(),
    }


class TestVerifyManifestSignature:
    def test_verify_valid(self, keypair):
        manifest = _issue_manifest([{"email": _SEAT1, "role": "admin"}], keypair["private_key_hex"])
        assert verify_manifest_signature(manifest, keypair["public_key_hex"])

    def test_verify_tampered_seat(self, keypair):
        manifest = _issue_manifest([{"email": _SEAT1, "role": "admin"}], keypair["private_key_hex"])
        manifest["seats"][0]["email"] = "intruder"
        assert not verify_manifest_signature(manifest, keypair["public_key_hex"])


class TestSyncSeats:
    def test_sync_valid_manifest(self, keypair, tmp_path):
        manifest = _issue_manifest(
            [{"email": _SEAT1, "role": "admin"}, {"email": _SEAT2, "role": "member"}],
            keypair["private_key_hex"],
        )
        seats_db = tmp_path / "seats.json"
        result = sync_seats(seats_db, manifest, license_limit=5, tier="team", admin=_ADMIN)
        assert result["status"] == "ok"
        assert len(result["added"]) == 2

    def test_sync_exceeds_limit(self, keypair, tmp_path):
        manifest = _issue_manifest(
            [{"email": "usera"}, {"email": "userb"}, {"email": "userc"}],
            keypair["private_key_hex"],
        )
        seats_db = tmp_path / "seats.json"
        result = sync_seats(seats_db, manifest, license_limit=2, tier="team", admin=_ADMIN)
        assert result["status"] == "partial"
        assert len(result["failed"]) == 1
        assert result["failed"][0]["email"] == "userc"
