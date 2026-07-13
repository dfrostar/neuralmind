"""Audit trail utilities for backend/security observability."""

from __future__ import annotations

import hashlib
import json
import os
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

AUDIT_FILE_NAME = "audit_events.jsonl"
_AUDIT_CACHE: dict[str, AuditTrail] = {}


# Actor resolution order: explicit > env var > OS user > "system"
def _resolve_actor(explicit: str | None = None) -> str:
    """Resolve the actor identity for an audit event.

    Resolution order:
    1. Explicit value passed by caller
    2. NEURALMIND_ACTOR environment variable
    3. OS login (LOGNAME / USERNAME)
    4. "system" (lowest fallback)
    """
    if explicit:
        return explicit
    env_actor = os.environ.get("NEURALMIND_ACTOR")
    if env_actor:
        return env_actor
    for key in ("LOGNAME", "USER"):
        val = os.environ.get(key)
        if val:
            return val
    return "system"


@dataclass
class AuditEvent:
    category: str
    action: str
    actor: str
    status: str
    target: str
    details: dict[str, Any]
    timestamp: str
    actor_role: str = ""
    ip_address: str = ""
    sha256: str = ""
    prev_sha256: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "category": self.category,
            "action": self.action,
            "actor": self.actor,
            "status": self.status,
            "target": self.target,
            "details": self.details,
            "actor_role": self.actor_role,
            "ip_address": self.ip_address,
            "sha256": self.sha256,
            "prev_sha256": self.prev_sha256,
        }

    def to_hashable_str(self) -> str:
        """Stable string for hashing — excludes sha256/prev_sha256 themselves."""
        d = self.to_dict()
        d.pop("sha256", None)
        d.pop("prev_sha256", None)
        return json.dumps(d, sort_keys=True, separators=(",", ":"))


class AuditTrail:
    """Append-only JSONL audit trail for a project with tamper-evident hash chain."""

    def __init__(self, project_path: str | Path):
        self.project_path = Path(project_path).resolve()
        self.events_file = self.project_path / ".neuralmind" / AUDIT_FILE_NAME

    def _last_sha256_from_file(self) -> str:
        """Read the last non-empty line's sha256, or '0'*64 if file is empty/legacy."""
        if not self.events_file.exists():
            return "0" * 64
        try:
            # Read all lines; find last non-empty; extract sha256
            with self.events_file.open(encoding="utf-8") as f:
                last = ""
                for line in f:
                    line = line.strip()
                    if line:
                        last = line
            if not last:
                return "0" * 64
            try:
                obj = json.loads(last)
                return obj.get("sha256") or "0" * 64
            except json.JSONDecodeError:
                return "0" * 64
        except OSError:
            return "0" * 64

    def append_event(
        self,
        category: str,
        action: str,
        actor: str | None = None,
        status: str = "success",
        target: str = "",
        details: dict[str, Any] | None = None,
        actor_role: str = "",
        ip_address: str = "",
    ) -> dict[str, Any]:
        actor = _resolve_actor(actor)
        prev_sha256 = self._last_sha256_from_file()
        event = AuditEvent(
            category=category,
            action=action,
            actor=actor,
            status=status,
            target=target,
            details=details or {},
            timestamp=datetime.now(timezone.utc).isoformat(),
            actor_role=actor_role,
            ip_address=ip_address,
            prev_sha256=prev_sha256,
            sha256="",
        )
        # SHA-256 of prev_hash + stable event serialization
        payload_str = prev_sha256 + event.to_hashable_str()
        event.sha256 = hashlib.sha256(payload_str.encode("utf-8")).hexdigest()

        payload = event.to_dict()
        self.events_file.parent.mkdir(parents=True, exist_ok=True)
        with self.events_file.open("a", encoding="utf-8") as file:
            file.write(json.dumps(payload, sort_keys=True) + "\n")
        return payload

    def read_events(self) -> list[dict[str, Any]]:
        if not self.events_file.exists():
            return []
        events: list[dict[str, Any]] = []
        with self.events_file.open(encoding="utf-8") as file:
            for line in file:
                line = line.strip()
                if not line:
                    continue
                try:
                    parsed = json.loads(line)
                    if isinstance(parsed, dict):
                        events.append(parsed)
                except json.JSONDecodeError:
                    continue
        return events

    def verify(self) -> dict[str, Any]:
        """Walk the hash chain, return status.

        Returns {ok: bool, first_bad_line: int|None, total: int}.
        Legacy lines without sha256 are accepted as trust-on-first-use seed.
        """
        events = self.read_events()
        if not events:
            return {"ok": True, "first_bad_line": None, "total": 0}

        prev_sha = "0" * 64
        for i, evt in enumerate(events, start=1):
            sha = evt.get("sha256", "")
            if not sha:
                # Legacy line — update prev_sha from its content (no chain check)
                prev_sha = "0" * 64  # reset; next line must carry prev_sha
                continue
            # Reconstruct what was hashed
            payload_str = prev_sha + json.dumps(
                {k: v for k, v in evt.items() if k not in ("sha256", "prev_sha256")},
                sort_keys=True,
                separators=(",", ":"),
            )
            expected = hashlib.sha256(payload_str.encode("utf-8")).hexdigest()
            if sha != expected:
                # Check if prev_sha matches
                if evt.get("prev_sha256") != prev_sha:
                    return {"ok": False, "first_bad_line": i, "total": len(events)}
                return {"ok": False, "first_bad_line": i, "total": len(events)}
            prev_sha = sha
        return {"ok": True, "first_bad_line": None, "total": len(events)}

    def search(
        self,
        category: str | None = None,
        action: str | None = None,
        actor: str | None = None,
        since: str | None = None,
        until: str | None = None,
        limit: int | None = None,
    ) -> list[dict[str, Any]]:
        """Filter events by field values. Case-insensitive substring match."""
        events = self.read_events()
        results = []
        for evt in events:
            if category and category.lower() not in evt.get("category", "").lower():
                continue
            if action and action.lower() not in evt.get("action", "").lower():
                continue
            if actor and actor.lower() not in evt.get("actor", "").lower():
                continue
            if since and evt.get("timestamp", "") < since:
                continue
            if until and evt.get("timestamp", "") > until:
                continue
            results.append(evt)
            if limit and len(results) >= limit:
                break
        return results

    def rotate(self, max_bytes: int = 100_000_000, keep_days: int = 90) -> dict[str, Any]:
        """Archive oversized file. Preserves hash-chain continuity.

        Returns {"rotated": bool, "archived_to": str|None, "deleted_archives": list}.
        """
        result = {"rotated": False, "archived_to": None, "deleted_archives": []}
        if not self.events_file.exists():
            return result
        size = self.events_file.stat().st_size
        if size < max_bytes:
            return result

        from datetime import datetime as _dt

        ts = _dt.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        archive_name = f"audit_events.{ts}.jsonl"
        archive_path = self.events_file.parent / archive_name

        # Rename current → archive (atomic on same filesystem)
        self.events_file.rename(archive_path)
        result["rotated"] = True
        result["archived_to"] = str(archive_path)

        # Clean old archives
        import re
        from datetime import timedelta as _td

        cutoff = _dt.now(timezone.utc) - _td(days=keep_days)
        for f in self.events_file.parent.glob("audit_events.*.jsonl"):
            m = re.match(r"audit_events\.(\d{8}_\d{6})\.jsonl", f.name)
            if m:
                try:
                    file_ts = _dt.strptime(m.group(1), "%Y%m%d_%H%M%S").replace(tzinfo=timezone.utc)
                    if file_ts < cutoff:
                        f.unlink()
                        result["deleted_archives"].append(str(f))
                except ValueError:
                    continue

        # Seed the new active file’s chain from the archived file’s final hash
        if archive_path.exists():
            last_sha = "0" * 64
            with archive_path.open("rb") as af:
                af.seek(0, 2)
                pos = af.tell()
                while pos > 0:
                    pos -= 1
                    af.seek(pos)
                    if af.read(1) == b"\n":
                        break
                last_line = af.readline().decode("utf-8").strip()
                if last_line:
                    try:
                        last_sha = json.loads(last_line).get("sha256") or "0" * 64
                    except json.JSONDecodeError:
                        pass
            # Write a chain-continuation marker
            with self.events_file.open("w", encoding="utf-8") as nf:
                marker = {
                    "timestamp": _dt.now(timezone.utc).isoformat(),
                    "category": "system",
                    "action": "rotation_continuation",
                    "actor": "system",
                    "status": "success",
                    "target": "",
                    "details": {"archive": str(archive_path.name)},
                    "prev_sha256": last_sha,
                }
                payload_str = last_sha + json.dumps(marker, sort_keys=True, separators=(",", ":"))
                marker["sha256"] = hashlib.sha256(payload_str.encode("utf-8")).hexdigest()
                nf.write(json.dumps(marker, sort_keys=True) + "\n")

        return result

    def export(
        self,
        format: str = "jsonl",
        category: str | None = None,
        action: str | None = None,
        actor: str | None = None,
        since: str | None = None,
        until: str | None = None,
    ) -> Iterable[str]:
        """Yield events in a SIEM-consumable format. One string per line."""
        events = self.search(
            category=category, action=action, actor=actor, since=since, until=until
        )
        for evt in events:
            if format == "cef":
                severity = 0 if evt.get("status") == "success" else 5
                actor_role = evt.get("actor_role", "") or "unknown"
                msg = (
                    f"CEF:0|NeuralMind|audit_trail|1.0|{evt.get('action', '')}|"
                    f"{evt.get('category', '')}|{severity}|"
                    f"src={evt.get('ip_address', '')} "
                    f"suser={evt.get('actor', '')} "
                    f"suserRole={actor_role} "
                    f"rt={evt.get('timestamp', '')} "
                    f"target={evt.get('target', '')} "
                    f"msg={json.dumps(evt.get('details', {}))}"
                )
                yield msg
            else:
                # jsonl: output as-is (already a dict → JSON line)
                yield json.dumps(evt, sort_keys=True)

    def nist_rmf_summary(self) -> dict[str, Any]:
        events = self.read_events()
        by_category: dict[str, int] = {}
        by_status: dict[str, int] = {}
        control_counts = {"AU": 0, "AC": 0, "SI": 0}

        for event in events:
            category = str(event.get("category", "unknown"))
            status = str(event.get("status", "unknown"))
            action = str(event.get("action", "")).lower()

            by_category[category] = by_category.get(category, 0) + 1
            by_status[status] = by_status.get(status, 0) + 1

            control_counts["AU"] += 1
            if category in {"security", "mcp", "auth", "rbac"} or any(
                token in action for token in ("access", "rbac", "deny", "allow", "rate_limit")
            ):
                control_counts["AC"] += 1
            if category in {"backend", "system", "admin"} or any(
                token in action for token in ("switch_backend", "build", "integrity", "failure")
            ):
                control_counts["SI"] += 1

        return {
            "events_total": len(events),
            "by_category": by_category,
            "by_status": by_status,
            "controls": control_counts,
        }


def get_audit_trail(project_path: str | Path) -> AuditTrail:
    key = str(Path(project_path).resolve())
    if key not in _AUDIT_CACHE:
        _AUDIT_CACHE[key] = AuditTrail(project_path)
    return _AUDIT_CACHE[key]
