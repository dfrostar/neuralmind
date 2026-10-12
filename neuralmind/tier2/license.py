# Copyright (c) 2026 Cheval-Volant LLC (d/b/a NeuralMind).
# Source-available under the NeuralMind Commercial Modules License
# (neuralmind/tier2/LICENSE) — NOT MIT. Free 1-seat use included; see LICENSING.md.
"""license.py — License validation for Tier 2 (Free + Team).

Two license tiers:
- "free": auto-issued on first run, self-signed, 1 seat, never expires
- "team": paid, Ed25519-signed by issuer, N seats, expires_at enforced

License JSON format:
{
  "tier": "free" | "team",
  "seats": 1 | 15,
  "issued_at": "ISO timestamp",
  "expires_at": "ISO timestamp",
  "issued_to": "self" | "acme-corp",
  "signature": "ed25519 hex sig (team) or 'self-signed' (free)"
}

Example:
    >>> from pathlib import Path
    >>> import tempfile
    >>> from neuralmind.tier2.license import issue_free_license, load_license
    >>> with tempfile.TemporaryDirectory() as td:
    ...     p = Path(td) / "license.json"
    ...     _ = issue_free_license(p)
    ...     load_license(p)
    'VALID'

See Also:
    - ``neuralmind.tier2.config`` — configures the license_file path
    - ``neuralmind.tier2.governance`` — governance gating on license status
    - ``tests/test_paid_seats.py`` — test cases and usage patterns
    - ``docs/wiki/Architecture.md#license`` — high-level design

Version:
    0.55.0
"""

from __future__ import annotations

import getpass
import hashlib
import json

# Ed25519 public key (32 bytes hex) — embedded issuer public key.
# Generated 2026-07-19. Fingerprint: d23aeb5ae460fede
# Override via NEURALMIND_ISSUER_PUBLIC_KEY_HEX env var for testing/multi-tenant.
import os as _os
import platform
import tempfile
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Literal

_ISSUER_PUBLIC_KEY_HEX = (
    _os.environ.get("NEURALMIND_ISSUER_PUBLIC_KEY_HEX")
    or "62a59c47bdef4c3b9dfeea6a74c90d42f966157f6d0969310ea7deb3bfcd365b"
)

LicenseStatus = Literal["VALID", "EXPIRED", "INVALID", "OFFLINE_OK", "TAMPERED"]

# Post-expiry grace window, fixed by the license agreement
# (docs/NEURALMIND-LICENSE-AGREEMENT.md §4.2 "Expiration"). Deliberately not
# configurable: a customer config must not extend a license past what the
# agreement grants.
GRACE_DAYS = 30


@dataclass
class LicenseInfo:
    """Immutable license data container.

    Args:
        tier: License tier (``"free"`` or ``"team"``).
        seats: Number of licensed seats.
        issued_at: ISO timestamp of issuance.
        expires_at: ISO timestamp of expiration, or ``"never"``.
        issued_to: Recipient identifier.
        signature: Ed25519 hex signature or ``"self-signed"``.
        raw: The raw dictionary from which this info was parsed.
    """

    tier: str
    seats: int
    issued_at: str
    expires_at: str
    issued_to: str
    signature: str
    raw: dict

    def to_dict(self) -> dict:
        """Convert to a plain dict for serialization.

        Returns:
            Dictionary with tier, seats, issued_at, expires_at, issued_to, signature.
        """
        return {
            "tier": self.tier,
            "seats": self.seats,
            "issued_at": self.issued_at,
            "expires_at": self.expires_at,
            "issued_to": self.issued_to,
            "signature": self.signature,
        }


class LicenseValidator:
    """Validate license files (free or team).

    Free tier: self-signed, no expiry, 1 seat
    Team tier: Ed25519-signed, has expiry, N seats

    Args:
        public_key_hex: Hex-encoded Ed25519 public key for signature verification.
            Can be a single key or a list of keys for rotation support.
        license_path: Path to the license JSON file.
        anti_tamper: Optional AntiTamper instance for clock-skew detection.
    """

    def __init__(
        self,
        public_key_hex: str | list[str],
        license_path: Path,
        anti_tamper: Any = None,
    ):
        if isinstance(public_key_hex, str):
            self._public_keys = [public_key_hex]
        else:
            self._public_keys = list(public_key_hex)
        self.license_path = Path(license_path)
        self._cached: LicenseInfo | None = None
        self.anti_tamper = anti_tamper

    def _load_raw(self) -> LicenseInfo | None:
        """Parse license.json.

        Returns:
            A ``LicenseInfo`` instance, or None if the file is missing or corrupt.
        """
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
        """Verify Ed25519 signature against any valid public key."""
        try:
            from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

            sig = lic.signature
            if not sig or sig == "self-signed":
                return False
            sig_bytes = bytes.fromhex(sig)
            msg_dict = {k: v for k, v in lic.raw.items() if k != "signature"}
            msg = json.dumps(msg_dict, sort_keys=True, separators=(",", ":"))
            for pk_hex in self._public_keys:
                pub_bytes = bytes.fromhex(pk_hex)
                pub_key = Ed25519PublicKey.from_public_bytes(pub_bytes)
                try:
                    pub_key.verify(sig_bytes, msg.encode("utf-8"))
                    return True
                except Exception:
                    continue
            return False
        except Exception:
            return False

    def _is_expired(self, lic: LicenseInfo) -> bool:
        """True if expires_at has passed.

        Free tier with ``expires_at="never"`` is never expired.
        """
        if lic.expires_at == "never":
            return False
        try:
            exp = datetime.fromisoformat(lic.expires_at.replace("Z", "+00:00"))
            return datetime.now(timezone.utc) > exp
        except ValueError:
            return True

    def _record_validation(self, lic: LicenseInfo, validated_at: str) -> None:
        """Persist validation timestamp to sidecar for clock-skew anti-tamper.

        Writes ``.last_valid`` next to the license file on every successful
        validation. Uses atomic write (tempfile + rename) to prevent
        partial-write corruption under concurrent multi-process access.
        """
        sidecar = self.license_path.with_suffix(".last_valid")
        try:
            fd, tmp_path = tempfile.mkstemp(
                dir=sidecar.parent, prefix=".last_valid-", suffix=".tmp"
            )
            try:
                with open(fd, "w", encoding="utf-8") as f:
                    f.write(validated_at)
                Path(tmp_path).replace(sidecar)
            except OSError:
                Path(tmp_path).unlink(missing_ok=True)
        except OSError:
            pass  # Sidecar is best-effort; validation still succeeds

    def _clock_set_back(self) -> bool:
        """True if the last recorded validation is later than the current time.

        Every successful validation writes its time to the ``.last_valid``
        sidecar, so a sidecar from the future means the system clock has been
        moved back since. A missing or unreadable sidecar proves nothing
        either way and returns False.
        """
        sidecar = self.license_path.with_suffix(".last_valid")
        try:
            ts = datetime.fromisoformat(sidecar.read_text(encoding="utf-8").strip())
            return ts > datetime.now(timezone.utc)
        except (OSError, ValueError, TypeError):  # TypeError: naive timestamp
            return False

    def _is_within_grace(self, lic: LicenseInfo) -> bool:
        """True if the license is expired but within its grace period.

        Grace runs ``GRACE_DAYS`` from ``expires_at``, as the license agreement
        grants, however long ago the software last ran. The one exception is
        a clock moved back since the last validation, which gets no grace.

        Grace is deliberately not also capped at ``GRACE_DAYS`` after the last
        validation: that cut the agreement's 30 days short for a customer who
        hadn't run the software in the weeks before expiry, and gave none with
        no validation on record, while adding no protection. A clock set back
        to before ``expires_at`` makes the license valid outright, grace or not.
        """
        if lic.expires_at == "never":
            return False  # Never-expired licenses don't need grace
        try:
            exp = datetime.fromisoformat(lic.expires_at.replace("Z", "+00:00"))
        except ValueError:
            return False
        if self._clock_set_back():
            return False
        return datetime.now(timezone.utc) <= exp + timedelta(days=GRACE_DAYS)

    def validate(self) -> LicenseStatus:
        """Return license status string.

        Free tier: valid if self-signed, 1 seat, not expired (usually never)
        Team tier: valid if Ed25519 signature verified, N seats, not expired

        When an ``AntiTamper`` instance is injected via ``anti_tamper``,
        this method also checks for timestamp regression (clock-skew attack)
        and records the validation event for future regression checks.

        Returns:
            One of ``"VALID"``, ``"EXPIRED"``, ``"INVALID"``, ``"OFFLINE_OK"``,
            or ``"TAMPERED"`` (only when ``anti_tamper`` is set and regression
            is detected).

        Example:
            >>> from pathlib import Path
            >>> import tempfile
            >>> from neuralmind.tier2.license import LicenseValidator, issue_free_license
            >>> with tempfile.TemporaryDirectory() as td:
            ...     p = Path(td) / "license.json"
            ...     _ = issue_free_license(p)
            ...     v = LicenseValidator("0" * 64, p)
            ...     v.validate()
            'VALID'
        """
        lic = self._load_raw()
        if lic is None:
            return "INVALID"  # No license = invalid (caller should issue free)

        # Wave 10B: Anti-tamper check (clock-skew detection)
        validated_at = datetime.now(timezone.utc).isoformat()
        if self.anti_tamper is not None:
            if self.anti_tamper.check_regression(
                license_id=lic.raw.get("license_id", "unknown"),
                validated_at=validated_at,
                expires_at_claimed=lic.expires_at,
            ):
                return "TAMPERED"

        status = "INVALID"
        if lic.tier == "free":
            if lic.seats != 1 or lic.signature != "self-signed":
                pass
            elif self._is_expired(lic):
                if self._is_within_grace(lic):
                    status = "OFFLINE_OK"
                else:
                    status = "EXPIRED"
            else:
                self._cached = lic
                status = "VALID"
        elif lic.tier == "team":
            if lic.seats <= 0 or not self._verify_signature(lic):
                pass
            elif self._is_expired(lic):
                if self._is_within_grace(lic):
                    status = "OFFLINE_OK"
                else:
                    status = "EXPIRED"
            else:
                self._cached = lic
                status = "VALID"

        # Record validation for clock-skew anti-tamper (both free + team)
        if status in ("VALID", "OFFLINE_OK"):
            self._record_validation(lic, validated_at)

        # Wave 10B: Record validation event (only on successful validation)
        if status == "VALID" and self.anti_tamper is not None:
            self.anti_tamper.record_validation(
                license_id=lic.raw.get("license_id", "unknown"),
                validated_at=validated_at,
                expires_at_claimed=lic.expires_at,
            )

        return status

    def status_dict(self) -> dict:
        """Return a detailed status dict for display.

        Returns:
            A dict with keys: status, tier, seats, expires_at, issued_to.

        Example:
            >>> from pathlib import Path
            >>> import tempfile
            >>> from neuralmind.tier2.license import LicenseValidator, issue_free_license
            >>> with tempfile.TemporaryDirectory() as td:
            ...     p = Path(td) / "license.json"
            ...     _ = issue_free_license(p)
            ...     v = LicenseValidator("0" * 64, p)
            ...     d = v.status_dict()
            ...     d["status"]
            'VALID'
        """
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
    """Shorthand: load + validate a license file.

    Args:
        path: Path to the license JSON file.
        public_key_hex: Hex-encoded Ed25519 public key (defaults to issuer key).

    Returns:
        One of ``"VALID"``, ``"EXPIRED"``, ``"INVALID"``, or ``"OFFLINE_OK"``.

    Example:
        >>> from pathlib import Path
        >>> import tempfile
        >>> from neuralmind.tier2.license import issue_free_license, load_license
        >>> with tempfile.TemporaryDirectory() as td:
        ...     p = Path(td) / "license.json"
        ...     _ = issue_free_license(p)
        ...     load_license(p)
        'VALID'
    """
    return LicenseValidator(public_key_hex, path).validate()


def issue_free_license(path: Path) -> LicenseInfo:
    """Issue a free tier license. Overwrites any existing file.

    Args:
        path: Path to write the license JSON file.

    Returns:
        The newly created ``LicenseInfo`` instance.

    Example:
        >>> from pathlib import Path
        >>> import tempfile
        >>> from neuralmind.tier2.license import issue_free_license
        >>> with tempfile.TemporaryDirectory() as td:
        ...     p = Path(td) / "license.json"
        ...     lic = issue_free_license(p)
        ...     lic.tier
        'free'
    """
    import tempfile

    now = datetime.now(timezone.utc).isoformat()
    lic = LicenseInfo(
        tier="free",
        seats=1,
        issued_at=now,
        expires_at="never",
        issued_to="self",
        signature="self-signed",
        raw={},
    )
    # Populate raw for consistent serialization
    lic.raw = lic.to_dict()
    path.parent.mkdir(parents=True, exist_ok=True)
    # Atomic write: create temp file + rename to avoid partial-write corruption
    # under concurrent access.
    fd, tmp_path = tempfile.mkstemp(dir=str(path.parent), suffix=".tmp")
    try:
        with open(fd, "w", encoding="utf-8") as f:
            json.dump(lic.to_dict(), f, indent=2)
        Path(tmp_path).replace(path)
    except Exception:
        # Clean up temp file on failure
        try:
            Path(tmp_path).unlink()
        except OSError:
            pass
        raise
    return lic


def generate_device_fingerprint() -> str:
    """Generate a stable(ish) device identifier from OS-provided machine-id.

    Returns:
        A 32-character hex string uniquely identifying this device.

    Example:
        >>> from neuralmind.tier2.license import generate_device_fingerprint
        >>> fp = generate_device_fingerprint()
        >>> len(fp)
        32
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

    # Fallback: hostname+user+OS composite
    composite = f"{platform.node()}|{getpass.getuser()}|{platform.system()}"
    return hashlib.sha256(composite.encode("utf-8")).hexdigest()[:32]
