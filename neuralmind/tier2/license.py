"""license.py — License validation for Tier 2.

License JSON format:
{
  "tier": "team",
  "seats": 15,
  "issued_at": "2026-07-19T00:00:00Z",
  "expires_at": "2027-07-19T00:00:00Z",
  "issued_to": "acme-corp",
  "signature": "ed25519_signature_hex"
}

Validation:
- Signature verified via Ed25519 (from embedded public key).
- Tier must be "team".
- Expiry checked against system clock + offline grace.
- Seat count read into config.
"""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

# Ed25519 public key (32 bytes hex) — embedded issuer public key.
# Replace with actual key in production. This is a TEST key.
_ISSUER_PUBLIC_KEY_HEX = "0000000000000000000000000000000000000000000000000000000000000001"

LicenseStatus = Literal["VALID", "EXPIRED", "INVALID", "OFFLINE_OK", "NO_LICENSE"]


@dataclass
class LicenseInfo:
    tier: str
    seats: int
    issued_at: str
    expires_at: str
    issued_to: str
    signature: str
    raw: dict

    def to_dict(self) -> dict:
        return {
            "tier": self.tier,
            "seats": self.seats,
            "issued_at": self.issued_at,
            "expires_at": self.expires_at,
            "issued_to": self.issued_to,
            "signature": self.signature,
        }


class LicenseValidator:
    """Validate Team tier license files.

    Falls back gracefully: missing license = NO_LICENSE (MIT path).
    Invalid signature = INVALID without crashing.
    """

    def __init__(self, public_key_hex: str, license_path: Path):
        self.public_key_hex = public_key_hex
        self.license_path = Path(license_path)
        self._cached: LicenseInfo | None = None

    def _load_raw(self) -> LicenseInfo | None:
        if not self.license_path.exists():
            return None
        try:
            with self.license_path.open(encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, json.JSONDecodeError):
            return None
        return LicenseInfo(
            tier=data.get("tier", ""),
            seats=int(data.get("seats", 0)),
            issued_at=data.get("issued_at", ""),
            expires_at=data.get("expires_at", ""),
            issued_to=data.get("issued_to", ""),
            signature=data.get("signature", ""),
            raw=data,
        )

    def _verify_signature(self, lic: LicenseInfo) -> bool:
        """Verify Ed25519 signature. Returns False on any error."""
        try:
            from cryptography.exceptions import InvalidSignature
            from cryptography.hazmat.primitives.asymmetric.ed25519 import (
                Ed25519PublicKey,
            )
            pub_bytes = bytes.fromhex(self.public_key_hex)
            pub_key = Ed25519PublicKey.from_public_bytes(pub_bytes)
            msg_dict = {k: v for k, v in lic.raw.items() if k != "signature"}
            msg = json.dumps(msg_dict, sort_keys=True, separators=(",", ":"))
            sig_bytes = bytes.fromhex(lic.signature)
            pub_key.verify(sig_bytes, msg.encode("utf-8"))
            return True
        except Exception:
            return False

    def _is_expired(self, lic: LicenseInfo) -> bool:
        """True if expires_at has passed."""
        try:
            exp = datetime.fromisoformat(lic.expires_at.replace("Z", "+00:00"))
            return datetime.now(timezone.utc) > exp
        except ValueError:
            return True

    def validate(self) -> LicenseStatus:
        """Return license status string.

        Status transitions:
        NO_LICENSE — license file missing or unreadable.
        INVALID — signature wrong, tier mismatch, or structural issue.
        EXPIRED — past expires_at.
        VALID — all checks pass.
        """
        lic = self._load_raw()
        if lic is None:
            return "NO_LICENSE"
        if lic.tier != "team":
            return "INVALID"
        if lic.seats <= 0:
            return "INVALID"
        if not self._verify_signature(lic):
            return "INVALID"
        if self._is_expired(lic):
            return "EXPIRED"
        self._cached = lic
        return "VALID"

    def status_dict(self) -> dict:
        """Return a detailed status dict for display."""
        status = self.validate()
        lic = self._cached or self._load_raw()
        if lic is None:
            return {
                "status": status,
                "tier": None,
                "seats": 0,
                "expires_at": None,
                "issued_to": None,
            }
        return {
            "status": status,
            "tier": lic.tier,
            "seats": lic.seats,
            "expires_at": lic.expires_at,
            "issued_to": lic.issued_to,
        }


def load_license(path: Path, public_key_hex: str = _ISSUER_PUBLIC_KEY_HEX) -> LicenseStatus:
    """Shorthand: load + validate a license file."""
    return LicenseValidator(public_key_hex, path).validate()


def generate_device_fingerprint() -> str:
    """Generate a stable(ish) device identifier from OS-provided machine-id.

    Falls back to hostname + user hash if /etc/machine-id is absent
    (e.g., containers, Windows WSL).
    """
    # Try /etc/machine-id (Linux systemd)
    machine_id_path = Path("/etc/machine-id")
    if machine_id_path.exists():
        try:
            return hashlib.sha256(machine_id_path.read_bytes()).hexdigest()[:32]
        except OSError:
            pass

    # Try /var/lib/dbus/machine-id (older Linux)
    dbus_id = Path("/var/lib/dbus/machine-id")
    if dbus_id.exists():
        try:
            return hashlib.sha256(dbus_id.read_bytes()).hexdigest()[:32]
        except OSError:
            pass

    # Fallback: hostname+user+OS composite — NOT stable across OS reinstalls,
    # but stable for the lifetime of this install.
    import platform
    import getpass
    composite = f"{platform.node()}|{getpass.getuser()}|{platform.system()}"
    return hashlib.sha256(composite.encode("utf-8")).hexdigest()[:32]
