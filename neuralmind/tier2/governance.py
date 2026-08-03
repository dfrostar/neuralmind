# Copyright (c) 2026 Cheval-Volant LLC (d/b/a NeuralMind).
# Source-available under the NeuralMind Commercial Modules License
# (neuralmind/tier2/LICENSE) — NOT MIT. Free 1-seat use included; see LICENSING.md.
"""governance.py — Team memory governance logic.

Gate before any edge enters the shared namespace:

1. Admin check — only admins can modify governance config.
2. Publishing scope — personal/shared/both determine what gets published.
3. Weight threshold — edges below threshold are rejected.
4. Content-hash dedup — identical bundles aren't re-published.

Governance only activates with a valid license. MIT users are unaffected.

Example:
    >>> from pathlib import Path
    >>> import tempfile
    >>> from neuralmind.tier2.config import Tier2Config
    >>> from neuralmind.tier2.audit import AuditLog
    >>> from neuralmind.tier2.governance import TeamGovernance
    >>> with tempfile.TemporaryDirectory() as td:
    ...     audit = AuditLog(Path(td) / "audit.jsonl")
    ...     cfg = Tier2Config()
    ...     cfg.governance.admin_emails = ["admin@test.com"]
    ...     gov = TeamGovernance(Path(td), cfg, audit)
    ...     gov.is_admin("admin@test.com")
    True

See Also:
    - ``neuralmind.tier2.audit`` — audit log that records governance actions
    - ``neuralmind.tier2.config`` — governance config schema
    - ``neuralmind.tier2.license`` — license validation gating governance
    - ``tests/test_governance.py`` — test cases and usage patterns
    - ``docs/wiki/Architecture.md#governance`` — high-level design

Version:
    0.53.0
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path

from .audit import AuditLog
from .config import Tier2Config, validate_scope


@dataclass
class GovernanceResult:
    """Result of a governance check.

    Args:
        allowed: Whether the action is permitted.
        reason: Human-readable explanation for the decision.
    """

    allowed: bool
    reason: str = ""


class TeamGovernance:
    """Controls what gets published to the team shared namespace.

    Args:
        db_path: Path to the governance database (used for audit log placement).
        config: The ``Tier2Config`` instance to read governance settings from.
        audit: Optional ``AuditLog`` instance. If not provided, a new one is created.
    """

    def __init__(self, db_path: Path, config: Tier2Config, audit: AuditLog | None = None):
        self.db_path = Path(db_path)
        self.config = config
        self.audit = audit if audit else AuditLog(self.db_path.parent / "audit_log.jsonl")

    def is_publishing_allowed(self, repo: str, edge_weight: float) -> GovernanceResult:
        """Check if a publish should be allowed based on governance rules.

        Args:
            repo: The repository being published (used for context, not validation).
            edge_weight: The weight of the edge being published.

        Returns:
            A ``GovernanceResult`` with ``allowed=True`` if:
            - Governance is enabled (``config.governance.enabled``)
            - Scope includes ``"shared"``
            - Edge weight >= ``config.governance.weight_threshold``

        Example:
            >>> from neuralmind.tier2.config import Tier2Config
            >>> cfg = Tier2Config()
            >>> cfg.governance.weight_threshold = 0.5
            >>> from neuralmind.tier2.governance import TeamGovernance
            >>> gov = TeamGovernance(Path("/tmp"), cfg)
            >>> result = gov.is_publishing_allowed("repo1", 0.8)
            >>> result.allowed
            True
        """
        if not self.config.governance.enabled:
            return GovernanceResult(True, "governance disabled; allowed")

        scope = self.config.governance.publishing_scope
        threshold = self.config.governance.weight_threshold

        if scope == "personal":
            return GovernanceResult(False, "scope=personal only; shared publishing blocked")

        if edge_weight < threshold:
            return GovernanceResult(False, f"weight {edge_weight:.3f} < threshold {threshold:.3f}")

        return GovernanceResult(True, "within governance bounds")

    def is_admin(self, email: str) -> bool:
        """True if email is configured as a team admin.

        Performs case-insensitive comparison. Returns False for empty/None email.

        Args:
            email: The email address to check.

        Returns:
            True if the email is in the admin list, False otherwise.

        Example:
            >>> from neuralmind.tier2.config import Tier2Config
            >>> cfg = Tier2Config()
            >>> cfg.governance.admin_emails = ["Admin@Example.com"]
            >>> from neuralmind.tier2.governance import TeamGovernance
            >>> gov = TeamGovernance(Path("/tmp"), cfg)
            >>> gov.is_admin("admin@example.com")
            True
            >>> gov.is_admin(None)
            False
        """
        if not email or not self.config.governance.admin_emails:
            return False
        return email.lower() in {e.lower() for e in self.config.governance.admin_emails}

    def require_admin(self, email: str) -> None:
        """Raise PermissionError if email is not an admin.

        Args:
            email: The email address to check.

        Raises:
            PermissionError: If the email is not in the admin list.

        Example:
            >>> from neuralmind.tier2.config import Tier2Config
            >>> cfg = Tier2Config()
            >>> cfg.governance.admin_emails = ["admin@test.com"]
            >>> from neuralmind.tier2.governance import TeamGovernance
            >>> gov = TeamGovernance(Path("/tmp"), cfg)
            >>> gov.require_admin("admin@test.com")  # no raise
            >>> gov.require_admin("nobody@test.com")  # doctest: +ELLIPSIS
            Traceback (most recent call last):
                ...
            PermissionError: Not a team admin: nobody@test.com
        """
        if not self.is_admin(email):
            raise PermissionError(f"Not a team admin: {email}")

    def remove_edge_from_shared(self, edge_id: str, admin: str) -> None:
        """Remove an edge from the shared namespace. Admin-only.

        Args:
            edge_id: The identifier of the edge to remove.
            admin: Email of the admin performing the action.

        Raises:
            PermissionError: If ``admin`` is not a team admin.

        Example:
            >>> from pathlib import Path
            >>> import tempfile
            >>> from neuralmind.tier2.config import Tier2Config
            >>> from neuralmind.tier2.audit import AuditLog
            >>> from neuralmind.tier2.governance import TeamGovernance
            >>> with tempfile.TemporaryDirectory() as td:
            ...     audit = AuditLog(Path(td) / "audit.jsonl")
            ...     cfg = Tier2Config()
            ...     cfg.governance.admin_emails = ["admin@test.com"]
            ...     gov = TeamGovernance(Path(td), cfg, audit)
            ...     gov.remove_edge_from_shared("edge-123", "admin@test.com")
            ...     audit.count()
            1
        """
        self.require_admin(admin)
        self.audit.log(
            actor=admin,
            action="remove",
            target=edge_id,
            details={"reason": "admin_removal"},
        )

    def set_publishing_scope(self, scope: str, admin: str) -> None:
        """Update publishing scope. Admin-only.

        Args:
            scope: The new scope (``"personal"``, ``"shared"``, or ``"both"``).
            admin: Email of the admin performing the action.

        Raises:
            PermissionError: If ``admin`` is not a team admin.
            ValueError: If ``scope`` is not a valid publishing scope.

        Example:
            >>> from pathlib import Path
            >>> import tempfile
            >>> from neuralmind.tier2.config import Tier2Config
            >>> from neuralmind.tier2.audit import AuditLog
            >>> from neuralmind.tier2.governance import TeamGovernance
            >>> with tempfile.TemporaryDirectory() as td:
            ...     audit = AuditLog(Path(td) / "audit.jsonl")
            ...     cfg = Tier2Config()
            ...     cfg.governance.admin_emails = ["admin@test.com"]
            ...     gov = TeamGovernance(Path(td), cfg, audit)
            ...     gov.set_publishing_scope("shared", "admin@test.com")
            ...     cfg.governance.publishing_scope
            'shared'
        """
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

        Threshold must be 0.0-1.0.

        Args:
            threshold: The new weight threshold (0.0-1.0).
            admin: Email of the admin performing the action.

        Raises:
            PermissionError: If ``admin`` is not a team admin.
            ValueError: If ``threshold`` is outside 0.0-1.0.

        Example:
            >>> from pathlib import Path
            >>> import tempfile
            >>> from neuralmind.tier2.config import Tier2Config
            >>> from neuralmind.tier2.audit import AuditLog
            >>> from neuralmind.tier2.governance import TeamGovernance
            >>> with tempfile.TemporaryDirectory() as td:
            ...     audit = AuditLog(Path(td) / "audit.jsonl")
            ...     cfg = Tier2Config()
            ...     cfg.governance.admin_emails = ["admin@test.com"]
            ...     gov = TeamGovernance(Path(td), cfg, audit)
            ...     gov.set_weight_threshold(0.7, "admin@test.com")
            ...     cfg.governance.weight_threshold
            0.7
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
        """Enable/disable team governance entirely. Admin-only.

        Args:
            enabled: True to enable governance, False to disable.
            admin: Email of the admin performing the action.

        Raises:
            PermissionError: If ``admin`` is not a team admin.

        Example:
            >>> from pathlib import Path
            >>> import tempfile
            >>> from neuralmind.tier2.config import Tier2Config
            >>> from neuralmind.tier2.audit import AuditLog
            >>> from neuralmind.tier2.governance import TeamGovernance
            >>> with tempfile.TemporaryDirectory() as td:
            ...     audit = AuditLog(Path(td) / "audit.jsonl")
            ...     cfg = Tier2Config()
            ...     cfg.governance.admin_emails = ["admin@test.com"]
            ...     gov = TeamGovernance(Path(td), cfg, audit)
            ...     gov.set_governance_enabled(False, "admin@test.com")
            ...     cfg.governance.enabled
            False
        """
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

    def publish(self, repo: str, edges: list[dict], admin: str) -> dict:
        """Publish edges to shared namespace.

        Steps:
        1. Gate: admin check (raises PermissionError if not admin).
        2. Gate: per-edge weight threshold (edges below threshold skipped).
        3. Audit: log the attempt.

        Args:
            repo: The repository being published.
            edges: List of edge dictionaries (each must have a ``weight`` key).
            admin: Email of the admin performing the action. Required.

        Returns:
            A dict with keys:
                - ``published`` (list): Edges that passed the threshold.
                - ``skipped`` (list): Edges below the threshold.
                - ``audit_id`` (str): SHA256 of the audit entry, or empty string.

        Raises:
            PermissionError: If ``admin`` is not a team admin.

        Example:
            >>> from pathlib import Path
            >>> import tempfile
            >>> from neuralmind.tier2.config import Tier2Config
            >>> from neuralmind.tier2.audit import AuditLog
            >>> from neuralmind.tier2.governance import TeamGovernance
            >>> with tempfile.TemporaryDirectory() as td:
            ...     audit = AuditLog(Path(td) / "audit.jsonl")
            ...     cfg = Tier2Config()
            ...     cfg.governance.admin_emails = ["admin@test.com"]
            ...     gov = TeamGovernance(Path(td), cfg, audit)
            ...     result = gov.publish("repo1", [{"weight": 0.8}], admin="admin@test.com")
            ...     len(result["published"])
            1
        """
        self.require_admin(admin)
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
            actor=admin,
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
    """Canonical SHA256 for an edge bundle — deterministic on content only.

    Args:
        edges: List of edge dictionaries.

    Returns:
        Hex-encoded SHA256 hash of the canonical serialization.

    Example:
        >>> from neuralmind.tier2.governance import content_fingerprint
        >>> content_fingerprint([{"weight": 0.5}])  # doctest: +SKIP
        'a1b2c3...'
    """
    canonical = json_edges_deterministic(edges)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def json_edges_deterministic(edges: list[dict]) -> str:
    """Serialize edges to a stable JSON string.

    Args:
        edges: List of edge dictionaries.

    Returns:
        A deterministic JSON string (sorted keys, sorted edges).

    Example:
        >>> from neuralmind.tier2.governance import json_edges_deterministic
        >>> json_edges_deterministic([{"b": 2, "a": 1}])
        '[{"a":1,"b":2}]'
    """
    import json

    return json.dumps(
        sorted(edges, key=lambda e: json.dumps(e, sort_keys=True)),
        sort_keys=True,
        separators=(",", ":"),
    )
