"""seats.py — Seat management for Team tier.

Each team seat is an email with an active/inactive flag. The seat limit comes
from the license (Tier2Config.seats). Adding a seat beyond the limit raises
SeatLimitError.
"""

from __future__ import annotations

import json
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class SeatLimitError(Exception):
    """Raised when attempting to add a seat beyond the license limit."""


@dataclass
class Seat:
    email: str
    active: bool = True
    added_at: str = ""
    last_active_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "email": self.email,
            "active": self.active,
            "added_at": self.added_at,
            "last_active_at": self.last_active_at,
        }

    @classmethod
    def from_dict(cls, data: dict) -> Seat:
        return cls(
            email=data["email"],
            active=data.get("active", True),
            added_at=data.get("added_at", ""),
            last_active_at=data.get("last_active_at", ""),
        )


class SeatManager:
    """Seat management backed by a JSON file in the config dir.

    Thread-safe via threading.Lock. Atomic writes via tempfile+rename.
    """

    def __init__(self, db_path: Path):
        import threading

        self.db_path = Path(db_path)
        self._lock = threading.Lock()
        self._seats: dict[str, Seat] = {}
        self._load()

    def _load(self) -> None:
        with self._lock:
            if not self.db_path.exists():
                self._seats = {}
                return
            try:
                with self.db_path.open(encoding="utf-8") as f:
                    raw = json.load(f)
                if isinstance(raw, list):
                    self._seats = {s["email"]: Seat.from_dict(s) for s in raw if "email" in s}
                else:
                    self._seats = {}
            except (OSError, json.JSONDecodeError):
                self._seats = {}

    def _save(self) -> None:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        data = [s.to_dict() for s in self._seats.values()]
        fd, tmp_path = tempfile.mkstemp(dir=self.db_path.parent, prefix=".seats-", suffix=".tmp")
        try:
            with open(fd, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
            Path(tmp_path).replace(self.db_path)
        except OSError:
            Path(tmp_path).unlink(missing_ok=True)
            raise

    def active_count(self) -> int:
        with self._lock:
            return sum(1 for s in self._seats.values() if s.active)

    def can_add_seat(self, license_limit: int, tier: str | None = None) -> bool:
        """True if active seats < license limit."""
        if tier == "free":
            return True
        with self._lock:
            return self.active_count() < license_limit

    def is_active_seat(self, email: str) -> bool:
        with self._lock:
            s = self._seats.get(email.strip().lower())
            return bool(s and s.active)

    def list_seats(self) -> list[Seat]:
        with self._lock:
            return sorted(self._seats.values(), key=lambda s: s.email)

    def add_seat(self, email: str, license_limit: int, tier: str | None = None) -> Seat:
        """Add a new seat. Idempotent if email already exists."""
        normalized = email.strip().lower()
        with self._lock:
            if normalized in self._seats:
                if self._seats[normalized].active:
                    return self._seats[normalized]
                if tier != "free" and self.active_count() >= license_limit:
                    raise SeatLimitError(
                        f"Seat limit reached: {self.active_count() + 1}/{license_limit}"
                    )
                self._seats[normalized].active = True
                self._seats[normalized].last_active_at = datetime.now(timezone.utc).isoformat()
                self._save()
                return self._seats[normalized]

            if not self.can_add_seat(license_limit, tier=tier):
                raise SeatLimitError(
                    f"Seat limit reached: {self.active_count() + 1}/{license_limit}"
                )
            now = datetime.now(timezone.utc).isoformat()
            seat = Seat(email=normalized, active=True, added_at=now, last_active_at=now)
            self._seats[normalized] = seat
            self._save()
            return seat

    def remove_seat(self, email: str) -> Seat:
        """Soft-delete a seat (deactivation)."""
        normalized = email.strip().lower()
        with self._lock:
            if normalized not in self._seats:
                raise KeyError(f"Seat not found: {normalized}")
            self._seats[normalized].active = False
            self._seats[normalized].last_active_at = datetime.now(timezone.utc).isoformat()
            self._save()
            return self._seats[normalized]


# Wave 13: Seat manifest sync

_DOMAIN_SEP = b"seat-manifest:v1"


def verify_manifest_signature(manifest: dict[str, Any], public_key_hex: str) -> bool:
    """Verify a seat manifest's Ed25519 signature."""
    try:
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

        pub_bytes = bytes.fromhex(public_key_hex)
        pub_key = Ed25519PublicKey.from_public_bytes(pub_bytes)
        payload = {k: v for k, v in manifest.items() if k != "signature"}
        canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
        sig_bytes = bytes.fromhex(manifest["signature"])
        pub_key.verify(sig_bytes, _DOMAIN_SEP + canonical.encode("utf-8"))
        return True
    except Exception:
        return False


def sync_seats(
    seats_db_path: Path,
    manifest: dict[str, Any],
    license_limit: int,
    tier: str,
    admin: str,
) -> dict[str, Any]:
    """Reconcile local seats from a verified manifest."""
    sm = SeatManager(seats_db_path)
    added = []
    failed = []

    for seat_data in manifest.get("seats", []):
        email = seat_data.get("email", "").strip().lower()
        if not email:
            continue
        try:
            sm.add_seat(email, license_limit, tier=tier)
            added.append(email)
        except SeatLimitError as e:
            failed.append({"email": email, "reason": str(e)})

    if failed:
        return {"status": "partial", "added": added, "failed": failed}
    return {"status": "ok", "added": added}
