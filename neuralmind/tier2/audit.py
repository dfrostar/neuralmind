# Copyright (c) 2026 Cheval-Volant LLC (d/b/a NeuralMind).
# Source-available under the NeuralMind Commercial Modules License
# (neuralmind/tier2/LICENSE) — NOT MIT. Free 1-seat use included; see LICENSING.md.
"""audit.py — Append-only hash-chained audit log for Team tier.

Tamper-evident hash chain: entry_N.hash = SHA256(entry_N.data + entry_{N-1}.hash)
Genesis hash (no predecessor): SHA256("neuralmind-team-audit-v1").

Appending is append-only (no update/delete API). Tampering with any historical
record breaks the chain (recompute doesn't match).

Example:
    >>> from pathlib import Path
    >>> import tempfile
    >>> from neuralmind.tier2.audit import AuditLog
    >>> with tempfile.TemporaryDirectory() as td:
    ...     log = AuditLog(Path(td) / "audit.jsonl")
    ...     _ = log.log(actor="admin@test", action="publish", target="repo1")
    ...     result = log.verify()
    ...     result["ok"]
    True

See Also:
    - ``neuralmind.tier2.governance`` — governance logic that writes audit entries
    - ``neuralmind.tier2.config`` — configures the audit_db path
    - ``tests/test_audit.py`` — test cases and usage patterns
    - ``docs/wiki/Architecture.md#audit`` — high-level design

Version:
    0.53.0
"""

from __future__ import annotations

import hashlib
import json
import threading
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

GENESIS_HASH = hashlib.sha256(b"neuralmind-team-audit-v1").hexdigest()

MAX_AUDIT_LINE_BYTES = 1_000_000  # Reject crafted DoS lines >1MB

AuditAction = Literal[
    "publish",
    "remove",
    "config_change",
    "seat_add",
    "seat_remove",
    "seat_sync",
    "license_activate",
    "self_hosted_init",
]


@dataclass
class AuditEntry:
    """A single immutable audit log entry.

    Args:
        actor: Email or identifier of the actor performing the action.
        action: The type of action performed (see ``AuditAction``).
        target: Optional target of the action (e.g., repo name, edge id).
        details: Optional dictionary of additional context.
        ts: ISO timestamp string (set by ``AuditLog.log`` if empty).
        prev_hash: SHA256 of the previous entry (set by ``AuditLog.log``).
        sha256: Computed hash of this entry (set by ``AuditLog.log``).
    """

    actor: str
    action: AuditAction
    target: str = ""
    details: dict[str, Any] | None = None
    ts: str = ""
    prev_hash: str = ""
    sha256: str = ""

    def compute_hash(self) -> str:
        """Compute SHA256 over (prev_hash + stable data serialization).

        Returns:
            The hex-encoded SHA256 hash of the entry.
        """
        data = json.dumps(self.data_dict(), sort_keys=True, separators=(",", ":"))
        payload = self.prev_hash + data
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def data_dict(self) -> dict[str, Any]:
        """Return the entry's data fields as a dict (without hashes).

        Returns:
            Dictionary with keys: ts, actor, action, target, details.
        """
        return {
            "ts": self.ts,
            "actor": self.actor,
            "action": self.action,
            "target": self.target,
            "details": self.details or {},
        }

    def to_dict(self) -> dict[str, Any]:
        """Return the full entry as a dict including hashes.

        Returns:
            Dictionary with all fields including ``prev_hash`` and ``sha256``.
        """
        d = self.data_dict()
        d["prev_hash"] = self.prev_hash
        d["sha256"] = self.sha256
        return d

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> AuditEntry:
        """Reconstruct an ``AuditEntry`` from a raw dict.

        Args:
            raw: Dictionary parsed from a JSONL line.

        Returns:
            A new ``AuditEntry`` instance.
        """
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
    """Project-scoped audit log backed by a JSONL file.

    Args:
        db_path: Path to the JSONL file backing this log.

    Raises:
        OSError: If the file exists but cannot be read (logged, not propagated).
    """

    def __init__(self, db_path: Path):
        self.db_path = Path(db_path)
        self._entries: list[AuditEntry] = []
        self._lock = threading.Lock()
        self._load()

    def _load(self) -> None:
        """Load entries from disk into memory.

        Skips malformed lines and oversized lines (>MAX_AUDIT_LINE_BYTES).
        """
        if not self.db_path.exists():
            self._entries = []
            return
        self._entries = []
        try:
            with self.db_path.open(encoding="utf-8") as f:
                for raw_line in f:
                    if len(raw_line) > MAX_AUDIT_LINE_BYTES:
                        continue  # Skip crafted oversized lines (DoS guard)
                    line = raw_line.strip()
                    if not line:
                        continue
                    try:
                        obj = json.loads(line)
                        if isinstance(obj, dict) and "sha256" in obj:
                            self._entries.append(AuditEntry.from_dict(obj))
                    except (json.JSONDecodeError, KeyError):
                        continue
        except (UnicodeDecodeError, OSError):
            self._entries = []

    def _save_append(self, entry: AuditEntry) -> None:
        """Append a single entry to the JSONL file.

        Args:
            entry: The entry to append.
        """
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with self.db_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry.to_dict(), sort_keys=True) + "\n")

    def _last_hash(self) -> str:
        """Return last entry's SHA256, or GENESIS_HASH if empty.

        Returns:
            The hash of the last entry, or ``GENESIS_HASH`` if no entries exist.
        """
        if not self._entries:
            return GENESIS_HASH
        return self._entries[-1].sha256

    def log(
        self,
        actor: str,
        action: AuditAction,
        target: str = "",
        details: dict[str, Any] | None = None,
    ) -> AuditEntry:
        """Append an audit entry with the correct hash chain.

        Thread-safe: acquires an internal lock to prevent concurrent log()
        calls from forking the chain on the same prev_hash.

        Args:
            actor: Email or identifier of the actor.
            action: The action type (see ``AuditAction``).
            target: Optional target of the action.
            details: Optional dictionary of additional context.

        Returns:
            The newly created ``AuditEntry`` with computed hash.

        Example:
            >>> from pathlib import Path
            >>> import tempfile
            >>> with tempfile.TemporaryDirectory() as td:
            ...     log = AuditLog(Path(td) / "audit.jsonl")
            ...     _ = log.log(actor="admin@test", action="publish", target="repo1")
            ...     entry = log.log(actor="admin@test", action="publish", target="repo1")
            ...     entry.sha256 != ""
            True
        """
        with self._lock:
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
        """Walk the hash chain, return ``{ok, first_bad_line, total}``.

        Args:
            fast: If True, stop at the first bad line. Otherwise verify all
                entries even after a failure (reports first bad, marks ok=False).

        Returns:
            A dict with keys:
                - ``ok`` (bool): True if the entire chain is valid.
                - ``first_bad_line`` (int | None): 1-based index of the first bad entry.
                - ``total`` (int): Total number of entries checked.

        Example:
            >>> from pathlib import Path
            >>> import tempfile
            >>> with tempfile.TemporaryDirectory() as td:
            ...     log = AuditLog(Path(td) / "audit.jsonl")
            ...     _ = log.log(actor="a", action="publish", target="t")
            ...     log.verify()
            {'ok': True, 'first_bad_line': None, 'total': 1}
        """
        if not self._entries:
            return {"ok": True, "first_bad_line": None, "total": 0}

        prev = GENESIS_HASH
        first_bad: int | None = None
        for i, entry in enumerate(self._entries, start=1):
            if entry.prev_hash != prev or entry.sha256 != entry.compute_hash():
                if first_bad is None:
                    first_bad = i
                if fast:
                    return {"ok": False, "first_bad_line": first_bad, "total": len(self._entries)}
            prev = entry.sha256
        return {
            "ok": first_bad is None,
            "first_bad_line": first_bad,
            "total": len(self._entries),
        }

    def export(
        self, since: float | None = None, until: float | None = None, actor: str | None = None
    ) -> list[AuditEntry]:
        """Export entries filtered by time range and/or actor.

        Args:
            since: Optional unix timestamp; entries before this are excluded.
            until: Optional unix timestamp; entries after this are excluded.
            actor: Optional case-insensitive substring to match against actor.

        Returns:
            A list of ``AuditEntry`` objects matching the filters.

        Example:
            >>> from pathlib import Path
            >>> import tempfile
            >>> with tempfile.TemporaryDirectory() as td:
            ...     log = AuditLog(Path(td) / "audit.jsonl")
            ...     _ = log.log(actor="admin@test", action="publish", target="repo1")
            ...     results = log.export(actor="admin")
            ...     len(results)
            1
        """
        results = []
        for entry in self._entries:
            if actor and actor.lower() not in entry.actor.lower():
                continue
            if since is not None:
                try:
                    ts_epoch = datetime.fromisoformat(entry.ts.replace("Z", "+00:00")).timestamp()
                    if ts_epoch < since:
                        continue
                except ValueError:
                    continue
            if until is not None:
                try:
                    ts_epoch = datetime.fromisoformat(entry.ts.replace("Z", "+00:00")).timestamp()
                    if ts_epoch > until:
                        continue
                except ValueError:
                    continue
            results.append(entry)
        return results

    def to_dicts(self) -> list[dict[str, Any]]:
        """Return all entries as plain dicts (for JSON serialization).

        Returns:
            A list of dictionaries, one per entry.
        """
        return [e.to_dict() for e in self._entries]

    def export_csv(self, path: Path, **filters: Any) -> int:
        """Export to CSV.

        Args:
            path: Destination file path.
            **filters: Optional filters passed to ``export()`` (since, until, actor).

        Returns:
            The number of rows written.

        Example:
            >>> from pathlib import Path
            >>> import tempfile
            >>> with tempfile.TemporaryDirectory() as td:
            ...     log = AuditLog(Path(td) / "audit.jsonl")
            ...     _ = log.log(actor="a", action="publish", target="t")
            ...     p = Path(td) / "out.csv"
            ...     log.export_csv(p)
            1
        """
        import csv

        entries = self.export(
            **{k: v for k, v in filters.items() if k in ("since", "until", "actor")}
        )
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["ts", "actor", "action", "target", "prev_hash", "sha256"])
            for e in entries:
                w.writerow([e.ts, e.actor, e.action, e.target, e.prev_hash, e.sha256])
        return len(entries)

    def export_json(self, path: Path, **filters: Any) -> int:
        """Export to JSON array.

        Args:
            path: Destination file path.
            **filters: Optional filters passed to ``export()`` (since, until, actor).

        Returns:
            The number of records written.

        Example:
            >>> from pathlib import Path
            >>> import tempfile
            >>> with tempfile.TemporaryDirectory() as td:
            ...     log = AuditLog(Path(td) / "audit.jsonl")
            ...     _ = log.log(actor="a", action="publish", target="t")
            ...     p = Path(td) / "out.json"
            ...     log.export_json(p)
            1
        """
        entries = self.export(
            **{k: v for k, v in filters.items() if k in ("since", "until", "actor")}
        )
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as f:
            json.dump([e.to_dict() for e in entries], f, indent=2)
        return len(entries)

    def count(self) -> int:
        """Return the number of entries in the log.

        Returns:
            Integer count of entries.
        """
        return len(self._entries)

    def latest(self) -> AuditEntry | None:
        """Return the most recent entry.

        Returns:
            The last ``AuditEntry`` or None if the log is empty.
        """
        return self._entries[-1] if self._entries else None
