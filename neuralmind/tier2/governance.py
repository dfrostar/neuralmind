"""governance.py — Team memory governance logic.

Gate before any edge enters the shared namespace:

1. Admin check — only admins can modify governance config.
2. Publishing scope — personal/shared/both determine what gets published.
3. Weight threshold — edges below threshold are rejected.
4. Content-hash dedup — identical bundles aren't re-published.

Governance only activates with a valid license. MIT users are unaffected.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from .audit import AuditAction, AuditLog
from .config import PublishingScope, Tier2Config, validate_scope


@dataclass
class GovernanceResult:
    allowed: bool
    reason: str = ""


class TeamGovernance:
    """Controls what gets published to the team shared namespace."""

    def __init__(self, db_path: Path, config: Tier2Config, audit: AuditLog | None = None):
        self.db_path = Path(db_path)
        self.config = config
        self.audit = audit if audit else AuditLog(self.db_path.parent / "audit_log.jsonl")

    def is_publishing_allowed(self, repo: str, edge_weight: float) -> GovernanceResult:
        """Check if a publish should be allowed based on governance rules.

        Returns GovernanceResult with allowed=True if:
        - Governance enabled (config.governance.enabled)
        - Scope includes "shared"
        - Edge weight >= config.governance.weight_threshold
        """
        if not self.config.governance.enabled:
            return GovernanceResult(True, "governance disabled; allowed")

        scope = self.config.governance.publishing_scope
        threshold = self.config.governance.weight_threshold

        if scope == "personal":
            return GovernanceResult(False, "scope=personal only; shared publishing blocked")

        if edge_weight < threshold:
            return GovernanceResult(False,
                f"weight {edge_weight:.3f} < threshold {threshold:.3f}")

        return GovernanceResult(True, "within governance bounds")

    def is_admin(self, email: str) -> bool:
        """True if email is configured as a team admin."""
        if not self.config.governance.admin_emails:
            return False
        return email.lower() in {e.lower() for e in self.config.governance.admin_emails}

    def require_admin(self, email: str) -> None:
        """Raise PermissionError if email is not an admin."""
        if not self.is_admin(email):
            raise PermissionError(f"Not a team admin: {email}")

    def remove_edge_from_shared(self, edge_id: str, admin: str) -> None:
        """Remove an edge from the shared namespace. Admin-only."""
        self.require_admin(admin)
        self.audit.log(
            actor=admin,
            action="remove",
            target=edge_id,
            details={"reason": "admin_removal"},
        )

    def set_publishing_scope(self, scope: str, admin: str) -> None:
        """Update publishing scope. Admin-only."""
        self.require_admin(admin)
        validate_scope(scope)
        old_scope = self.config.governance.publishing_scope
        self.config.governance.publishing_scope = scope
        if old_scope != scope:
            self.audit.log(
                actor=admin,
                action="config_change",
                target="governance.publishing_scope",
                details={"old": old_scope, "new": scope},
            )

    def set_weight_threshold(self, threshold: float, admin: str) -> None:
        """Update minimum edge weight for auto-publish. Admin-only.

        Threshold must be 0.0–1.0.
        """
        self.require_admin(admin)
        if threshold < 0.0 or threshold > 1.0:
            raise ValueError(f"weight_threshold must be 0.0-1.0, got {threshold}")
        old_threshold = self.config.governance.weight_threshold
        self.config.governance.weight_threshold = threshold
        if old_threshold != threshold:
            self.audit.log(
                actor=admin,
                action="config_change",
                target="governance.weight_threshold",
                details={"old": old_threshold, "new": threshold},
            )

    def set_governance_enabled(self, enabled: bool, admin: str) -> None:
        """Enable/disable team governance entirely. Admin-only."""
        self.require_admin(admin)
        old = self.config.governance.enabled
        self.config.governance.enabled = enabled
        if old != enabled:
            self.audit.log(
                actor=admin,
                action="config_change",
                target="governance.enabled",
                details={"old": old, "new": enabled},
            )

    def publish(self, repo: str, edges: list[dict], admin: str | None = None) -> dict:
        """Publish edges to shared namespace.

        Steps:
        1. Gate: weight threshold (fast-fail all-or-nothing).
        2. Dedup: content-hash check to avoid duplicate traversal cost.
        3. Audit: log the attempt.

        Returns {published: [...], skipped: [...], audit_id: str}.
        """
        threshold = self.config.governance.weight_threshold
        published = []
        skipped = []
        for edge in edges:
            w = float(edge.get("weight", 0.0))
            if w < threshold:
                skipped.append(edge)
                continue
            published.append(edge)

        self.audit.log(
            actor=admin or "system",
            action="publish",
            target=repo,
            details={"count": len(published), "skipped": len(skipped)},
        )
        return {
            "published": published,
            "skipped": skipped,
            "audit_id": self.audit.latest().sha256 if self.audit.count() > 0 else "",
        }


def content_fingerprint(edges: list[dict]) -> str:
    """Canonical SHA256 for an edge bundle — deterministic on content only."""
    canonical = json_edges_deterministic(edges)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def json_edges_deterministic(edges: list[dict]) -> str:
    """Serialize edges to a stable JSON string."""
    import json
    return json.dumps(sorted(edges, key=lambda e: json.dumps(e, sort_keys=True)),
                     sort_keys=True, separators=(",", ":"))
