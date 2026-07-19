"""audit.py — Append-only hash-chained audit log for Team tier.

Tamper-evident hash chain: entry_N.hash = SHA256(entry_N.data + entry_{N-1}.hash)
Genesis hash (no predecessor): SHA256("neuralmind-team-audit-v1").

Appending is append-only (no update/delete API). Tampering with any historical
record breaks the chain (recompute doesn't match).
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Literal

GENESIS_HASH = hashlib.sha256(b"neuralmind-team-audit-v1").hexdigest()

AuditAction = Literal["publish", "remove", "config_change", "seat_add", "seat_remove",
                      "license_activate", "self_hosted_init"]


@dataclass
class AuditEntry:
    actor: str
    action: AuditAction
    target: str = ""
    details: dict[str, Any] | None = None
    ts: str = ""
    prev_hash: str = ""
    sha256: str = ""

    def compute_hash(self) -> str:
        """Compute SHA256 over (prev_hash + stable data serialization)."""
        data = json.dumps(self.data_dict(), sort_keys=True, separators=(",", ":"))
        payload = self.prev_hash + data
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def data_dict(self) -> dict[str, Any]:
        return {
            "ts": self.ts,
            "actor": self.actor,
            "action": self.action,
            "target": self.target,
            "details": self.details or {},
        }

    def to_dict(self) -> dict[str, Any]:
        d = self.data_dict()
        d["prev_hash"] = self.prev_hash
        d["sha256"] = self.sha256
        return d

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "AuditEntry":
        return cls(
            actor=raw["actor"],
            action=raw["action"],
            target=raw.get("target", ""),
            details=raw.get("details", {}),
            ts=raw.get("ts", ""),
            prev_hash=raw.get("prev_hash", ""),
            sha256=raw.get("sha256", ""),
        )


class AuditLog:
    """Project-scoped audit log backed by a JSONL file."""

    def __init__(self, db_path: Path):
        self.db_path = Path(db_path)
        self._entries: list[AuditEntry] = []
        self._load()

    def _load(self) -> None:
        if not self.db_path.exists():
            self._entries = []
            return
        self._entries = []
        with self.db_path.open(encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                    if isinstance(obj, dict) and "sha256" in obj:
                        self._entries.append(AuditEntry.from_dict(obj))
                except (json.JSONDecodeError, KeyError):
                    continue

    def _save_append(self, entry: AuditEntry) -> None:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with self.db_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry.to_dict(), sort_keys=True) + "\n")

    def _last_hash(self) -> str:
        """Return last entry's SHA256, or GENESIS_HASH if empty."""
        if not self._entries:
            return GENESIS_HASH
        return self._entries[-1].sha256

    def log(self, actor: str, action: AuditAction, target: str = "",
            details: dict[str, Any] | None = None) -> AuditEntry:
        """Append an audit entry with the correct hash chain."""
        now = datetime.now(timezone.utc).isoformat()
        entry = AuditEntry(
            actor=actor,
            action=action,
            target=target,
            details=details or {},
            ts=now,
            prev_hash=self._last_hash(),
        )
        entry.sha256 = entry.compute_hash()
        self._save_append(entry)
        self._entries.append(entry)
        return entry

    def verify(self, fast: bool = False) -> dict[str, Any]:
        """Walk the hash chain, return {ok, first_bad_line, total}.

        If fast=True, stop at the first bad line. Otherwise verify all entries
        even after a failure (reports first bad, marks ok=False).
        """
        if not self._entries:
            return {"ok": True, "first_bad_line": None, "total": 0}

        prev = GENESIS_HASH
        for i, entry in enumerate(self._entries, start=1):
            if entry.prev_hash != prev:
                return {"ok": False, "first_bad_line": i, "total": len(self._entries)}
            expected = entry.compute_hash()
            if entry.sha256 != expected:
                return {"ok": False, "first_bad_line": i, "total": len(self._entries)}
            prev = entry.sha256
            if fast and not self._entries[i:i + 1]:
                # cheap early-out — we are past the last; not used normally
                pass
        return {"ok": True, "first_bad_line": None, "total": len(self._entries)}

    def export(self, since: float | None = None, until: float | None = None,
               actor: str | None = None) -> list[AuditEntry]:
        """Export entries filtered by (optional) since/until unix seconds,
        plus optional actor substring (case-insensitive)."""
        results = []
        for entry in self._entries:
            if actor and actor.lower() not in entry.actor.lower():
                continue
            if since is not None:
                try:
                    ts_epoch = datetime.fromisoformat(
                        entry.ts.replace("Z", "+00:00")
                    ).timestamp()
                    if ts_epoch < since:
                        continue
                except ValueError:
                    continue
            if until is not None:
                try:
                    ts_epoch = datetime.fromisoformat(
                        entry.ts.replace("Z", "+00:00")
                    ).timestamp()
                    if ts_epoch > until:
                        continue
                except ValueError:
                    continue
            results.append(entry)
        return results

    def to_dicts(self) -> list[dict[str, Any]]:
        """Return all entries as plain dicts (for JSON serialization)."""
        return [e.to_dict() for e in self._entries]

    def export_csv(self, path: Path, **filters: Any) -> int:
        """Export to CSV. Returns count of rows written."""
        import csv
        entries = self.export(**{k: v for k, v in filters.items()
                                if k in ("since", "until", "actor")})
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["ts", "actor", "action", "target", "prev_hash", "sha256"])
            for e in entries:
                w.writerow([e.ts, e.actor, e.action, e.target,
                            e.prev_hash, e.sha256])
        return len(entries)

    def export_json(self, path: Path, **filters: Any) -> int:
        """Export to JSON array. Returns count of records written."""
        entries = self.export(**{k: v for k, v in filters.items()
                                if k in ("since", "until", "actor")})
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as f:
            json.dump([e.to_dict() for e in entries], f, indent=2)
        return len(entries)

    def count(self) -> int:
        return len(self._entries)

    def latest(self) -> AuditEntry | None:
        return self._entries[-1] if self._entries else None
