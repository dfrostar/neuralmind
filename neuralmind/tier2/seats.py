"""seats.py — Seat management for Team tier.

Each team seat is an email with an active/inactive flag. The seat limit comes
from the license (Tier2Config.seats). Adding a seat beyond the limit raises
SeatLimitError.
"""

from __future__ import annotations

import json
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

    Thread-safe for the single-admin CLI pattern. Concurrent writes are not a
    concern in this deployment model.
    """

    def __init__(self, db_path: Path):
        self.db_path = Path(db_path)
        self._seats: dict[str, Seat] = {}
        self._load()

    def _load(self) -> None:
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
        with self.db_path.open("w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

    def active_count(self) -> int:
        return sum(1 for s in self._seats.values() if s.active)

    def can_add_seat(self, license_limit: int) -> bool:
        """True if active seats < license limit."""
        return self.active_count() < license_limit

    def is_active_seat(self, email: str) -> bool:
        s = self._seats.get(email.lower())
        return bool(s and s.active)

    def list_seats(self) -> list[Seat]:
        return sorted(self._seats.values(), key=lambda s: s.email)

    def add_seat(self, email: str, license_limit: int) -> Seat:
        """Add a new seat. Idempotent if email already exists.

        Raises SeatLimitError if beyond limit.
        """
        normalized = email.lower()
        if normalized in self._seats:
            if self._seats[normalized].active:
                return self._seats[normalized]  # idempotent
            # Reactivate
            if self.active_count() >= license_limit and self._seats[normalized].active is False:
                raise SeatLimitError(
                    f"Seat limit reached: {self.active_count() + 1}/{license_limit}"
                )
            self._seats[normalized].active = True
            self._seats[normalized].last_active_at = datetime.now(timezone.utc).isoformat()
            self._save()
            return self._seats[normalized]

        if not self.can_add_seat(license_limit):
            raise SeatLimitError(f"Seat limit reached: {self.active_count() + 1}/{license_limit}")
        now = datetime.now(timezone.utc).isoformat()
        seat = Seat(email=normalized, active=True, added_at=now, last_active_at=now)
        self._seats[normalized] = seat
        self._save()
        return seat

    def remove_seat(self, email: str) -> Seat:
        """Soft-delete a seat (deactivation). Does not hard-delete to preserve audit trail.

        Returns the modified Seat.
        """
        normalized = email.lower()
        if normalized not in self._seats:
            raise KeyError(f"Seat not found: {email}")
        self._seats[normalized].active = False
        self._seats[normalized].last_active_at = datetime.now(timezone.utc).isoformat()
        self._save()
        return self._seats[normalized]
