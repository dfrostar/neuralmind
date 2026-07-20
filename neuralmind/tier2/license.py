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
    - ``tests/test_license.py`` — test cases and usage patterns
    - ``docs/wiki/Architecture.md#license`` — high-level design

Version:
    0.55.0
"""

from __future__ import annotations

import getpass
import hashlib
import json
import platform
import tempfile
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Literal

# Ed25519 public key (32 bytes hex) — embedded issuer public key.
# Generated 2026-07-19. Fingerprint: d23aeb5ae460fede
_ISSUER_PUBLIC_KEY_HEX = "62a59c47bdef4c3b9dfeea6a74c90d42f966157f6d0969310ea7deb3bfcd365b"

LicenseStatus = Literal["VALID", "EXPIRED", "INVALID", "OFFLINE_OK", "TAMPERED"]


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
        license_path: Path to the license JSON file.
        anti_tamper: Optional AntiTamper instance for clock-skew detection.
            When provided, each validate() checks for timestamp regression
            and records the validation event. When None, validation is
            identical to pre-Wave 10B behavior.
    """

    def __init__(
        self,
        public_key_hex: str,
        license_path: Path,
        anti_tamper: Any = None,
    ):
        self.public_key_hex = public_key_hex
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
        """Verify Ed25519 signature (team tier).

        Args:
            lic: The ``LicenseInfo`` to verify.

        Returns:
            True if the signature is valid, False on any error.
        """
        try:
            from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

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
        """True if expires_at has passed.

        Free tier with ``expires_at="never"`` is never expired.

        Args:
            lic: The ``LicenseInfo`` to check.

        Returns:
            True if the license has expired, False otherwise.
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

    def _get_last_validation(self) -> float | None:
        """Read last recorded validation timestamp.

        Returns:
            Unix timestamp of last successful validation, or None if absent.

        Raises no errors — missing/corrupt sidecar returns None (treated as
        "no prior validation" = first validation).
        """
        sidecar = self.license_path.with_suffix(".last_valid")
        if not sidecar.exists():
            return None
        try:
            ts = datetime.fromisoformat(sidecar.read_text(encoding="utf-8"))
            # Reject future timestamps (clock-set-back anti-tamper)
            now = datetime.now(timezone.utc)
            if ts > now:
                return None  # Clock was set back — untrustworthy
            return ts.timestamp()
        except (ValueError, OSError):
            return None

    def _is_within_grace(self, lic: LicenseInfo) -> bool:
        """True if license is expired but within the dual-bound grace window.

        Dual-bound = min(expires_at + grace_days, last_validation + grace_days).
        Either bound alone is exploitable:
        - expires_at + grace alone → clock-set-back extends indefinitely.
        - last_validation + grace alone → long-dead license keeps extending.
        """
        if lic.expires_at == "never":
            return False  # Never-expired licenses don't need grace
        try:
            exp = datetime.fromisoformat(lic.expires_at.replace("Z", "+00:00"))
        except ValueError:
            return False
        now = datetime.now(timezone.utc)
        last_val = self._get_last_validation()
        if last_val is None:
            return False  # No record — no grace
        last_val_dt = datetime.fromtimestamp(last_val, tz=timezone.utc)
        gd = getattr(self, "offline_grace_days", 30)
        grace_deadline = min(
            exp + timedelta(days=gd),
            last_val_dt + timedelta(days=gd),
        )
        return now <= grace_deadline

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
            if lic.seats != 1:
                pass
            elif lic.signature != "self-signed":
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
            if lic.seats <= 0:
                pass
            elif not self._verify_signature(lic):
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
    with path.open("w", encoding="utf-8") as f:
        json.dump(lic.to_dict(), f, indent=2)
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
