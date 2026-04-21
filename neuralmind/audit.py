"""Audit trail utilities for backend/security observability."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

AUDIT_FILE_NAME = "audit_events.jsonl"
_AUDIT_CACHE: dict[str, AuditTrail] = {}


@dataclass
class AuditEvent:
    category: str
    action: str
    actor: str
    status: str
    target: str
    details: dict[str, Any]
    timestamp: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "category": self.category,
            "action": self.action,
            "actor": self.actor,
            "status": self.status,
            "target": self.target,
            "details": self.details,
        }


class AuditTrail:
    """Append-only JSONL audit trail for a project."""

    def __init__(self, project_path: str | Path):
        self.project_path = Path(project_path).resolve()
        self.events_file = self.project_path / ".neuralmind" / AUDIT_FILE_NAME

    def append_event(
        self,
        category: str,
        action: str,
        actor: str = "system",
        status: str = "success",
        target: str = "",
        details: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        event = AuditEvent(
            category=category,
            action=action,
            actor=actor,
            status=status,
            target=target,
            details=details or {},
            timestamp=datetime.now(timezone.utc).isoformat(),
        )
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
            if category in {"security", "mcp"} or any(
                token in action for token in ("access", "rbac", "deny", "allow", "rate_limit")
            ):
                control_counts["AC"] += 1
            if category in {"backend", "system"} or any(
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
