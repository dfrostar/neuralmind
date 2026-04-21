"""Audit trail utilities and NIST RMF reporting."""

from __future__ import annotations

import json
import uuid
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


@dataclass
class AuditEvent:
    event_id: str
    timestamp: str
    category: str
    action: str
    actor: str
    status: str
    target: str = ""
    details: dict[str, Any] = field(default_factory=dict)


class AuditTrail:
    """Append-only JSONL audit trail."""

    def __init__(self, project_path: str | Path, audit_file: str | Path | None = None):
        self.project_path = Path(project_path)
        if audit_file is None:
            audit_file = self.project_path / "graphify-out" / "audit" / "audit_trail.jsonl"
        self.audit_file = Path(audit_file)
        self.audit_file.parent.mkdir(parents=True, exist_ok=True)

    def log_event(
        self,
        category: str,
        action: str,
        actor: str = "system",
        status: str = "success",
        target: str = "",
        details: dict[str, Any] | None = None,
    ) -> AuditEvent:
        event = AuditEvent(
            event_id=str(uuid.uuid4()),
            timestamp=datetime.now(UTC).isoformat(),
            category=category,
            action=action,
            actor=actor,
            status=status,
            target=target,
            details=details or {},
        )
        with open(self.audit_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(asdict(event), default=str) + "\n")
        return event

    def list_events(self, category: str | None = None, status: str | None = None) -> list[dict[str, Any]]:
        if not self.audit_file.exists():
            return []
        events: list[dict[str, Any]] = []
        with open(self.audit_file, encoding="utf-8") as f:
            for line in f:
                event = json.loads(line)
                if category and event.get("category") != category:
                    continue
                if status and event.get("status") != status:
                    continue
                events.append(event)
        return events

    def generate_nist_rmf_report(self) -> dict[str, Any]:
        events = self.list_events()
        categories: dict[str, int] = {}
        statuses: dict[str, int] = {}
        controls: dict[str, int] = {"AC-3": 0, "AU-2": 0, "AU-12": 0, "SI-4": 0}
        for event in events:
            category = str(event.get("category", "unknown"))
            status = str(event.get("status", "unknown"))
            categories[category] = categories.get(category, 0) + 1
            statuses[status] = statuses.get(status, 0) + 1
            if category == "security":
                controls["AC-3"] += 1
                if event.get("action") == "rate_limit_check":
                    controls["SI-4"] += 1
            if category in {"security", "audit", "backend"}:
                controls["AU-2"] += 1
                controls["AU-12"] += 1

        return {
            "rmf_step": "monitor",
            "total_events": len(events),
            "category_counts": categories,
            "status_counts": statuses,
            "controls": controls,
            "generated_at": datetime.now(UTC).isoformat(),
        }
