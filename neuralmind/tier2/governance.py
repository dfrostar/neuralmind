# Copyright (c) 2026 Cheval-Volant LLC (d/b/a NeuralMind).
# Source-available under the NeuralMind Commercial Modules License
# (neuralmind/tier2/LICENSE) — NOT MIT. Free 1-seat use included; see LICENSING.md.
"""governance.py — Team memory governance logic.

Gate before any edge enters the shared namespace:

1. Admin check — only admins can modify governance config.
2. Publishing scope — personal/shared/both determine what gets published.
3. Weight threshold — edges below threshold are rejected.
4. Content-hash dedup — identical bundles aren't re-published.

Where it is enforced (``neuralmind.team_memory`` calls in here):

- ``neuralmind memory publish`` reads :func:`load_publish_policy`. Scope
  ``personal`` refuses to publish; ``shared`` publishes only the team
  baseline (the ``shared`` namespace); ``both`` publishes personal + shared.
  Synapse edges below ``weight_threshold`` are left out of the bundle.
- Publishes, imports, review approvals/rejections and admin removals are
  written to the hash-chained audit log (:func:`record_team_event`).
- ``team governance remove-edge`` deletes the association from ``shared``
  memory and retracts it in the committed bundle, so teammates drop it too.

Governance runs under any valid license, including the auto-issued free
1-seat license — a paid Team license adds seats (5-50) and support, not
hidden features. Users who never run ``neuralmind team`` or ``neuralmind
onboarding`` (no tier2 config file) are unaffected: nothing is gated or
audited.

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

import getpass
import hashlib
import logging
import os
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from . import config as config_mod
from .audit import AuditLog
from .config import Tier2Config, validate_scope

logger = logging.getLogger(__name__)


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

    def remove_edge_from_shared(
        self,
        source: str,
        target: str,
        admin: str,
        *,
        store: Any,
        project_path: str | Path,
    ) -> dict:
        """Stop sharing one association. Admin-only.

        Deletes the edge between ``source`` and ``target`` (and transitions
        between them) from the project's ``shared`` namespace, and retracts
        it in the committed team bundle: the pair leaves the bundle, is
        listed under ``retracted``, and the bundle's content hash changes —
        so each teammate's next session deletes it from their ``shared``
        memory too, and no later ``memory publish`` re-adds it. The removal
        is written to the audit log.

        Args:
            source: One node of the association.
            target: The other node.
            admin: Email of the admin performing the action.
            store: The project's ``SynapseStore``.
            project_path: Project root (where the team bundle lives).

        Returns:
            Counts from :func:`neuralmind.team_memory.retract_team_edge`.

        Raises:
            PermissionError: If ``admin`` is not a team admin.

        Example:
            >>> from pathlib import Path
            >>> import tempfile
            >>> from neuralmind.synapses import SynapseStore, default_db_path
            >>> from neuralmind.tier2.config import Tier2Config
            >>> from neuralmind.tier2.audit import AuditLog
            >>> from neuralmind.tier2.governance import TeamGovernance
            >>> with tempfile.TemporaryDirectory() as td:
            ...     audit = AuditLog(Path(td) / "audit.jsonl")
            ...     cfg = Tier2Config()
            ...     cfg.governance.admin_emails = ["admin@test.com"]
            ...     gov = TeamGovernance(Path(td), cfg, audit)
            ...     store = SynapseStore(default_db_path(td))
            ...     _ = store.import_edges([("a.py", "b.py", 0.9, 3)], namespace="shared")
            ...     result = gov.remove_edge_from_shared(
            ...         "a.py", "b.py", "admin@test.com", store=store, project_path=td
            ...     )
            ...     (result["removed_from_store"], audit.count())
            (1, 1)
        """
        self.require_admin(admin)
        from ..team_memory import retract_team_edge

        result = retract_team_edge(project_path, store, source, target)
        self.audit.log(
            actor=admin,
            action="remove",
            target=f"{source} -> {target}",
            details={
                "reason": "admin_removal",
                "project": str(Path(project_path).resolve()),
                "removed_from_store": result["removed_from_store"],
                "removed_from_bundle": result["removed_from_bundle"],
                "bundle": result["bundle"],
            },
        )
        return result

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


# --------------------------------------------------------------------------- #
# Enforcement entry points for the team-memory flow (neuralmind.team_memory)
# --------------------------------------------------------------------------- #

# Which learned-memory namespaces each publishing scope lets into the bundle.
# ``personal`` publishes nothing: memory stays on each developer's machine.
SCOPE_NAMESPACES: dict[str, tuple[str, ...]] = {
    "personal": (),
    "shared": ("shared",),
    "both": ("personal", "shared"),
}


@dataclass(frozen=True)
class PublishPolicy:
    """The governance settings ``neuralmind memory publish`` enforces.

    Args:
        scope: ``"personal"`` (publishing blocked), ``"shared"`` (only the team
            baseline is published) or ``"both"`` (personal + shared).
        weight_threshold: Synapse edges below this weight stay out of the bundle.
    """

    scope: str
    weight_threshold: float

    @property
    def blocks_publishing(self) -> bool:
        """True when the scope keeps every association on its machine."""
        return not self.source_namespaces

    @property
    def source_namespaces(self) -> tuple[str, ...]:
        """Namespaces whose associations may enter the team bundle."""
        return SCOPE_NAMESPACES.get(self.scope, ())

    def to_dict(self) -> dict[str, Any]:
        return {"scope": self.scope, "weight_threshold": self.weight_threshold}


def _config_file(path: str | Path | None = None) -> Path:
    # Read DEFAULT_CONFIG_PATH at call time so NEURALMIND_CONFIG_DIR overrides
    # and test monkeypatches take effect.
    return Path(path) if path else Path(config_mod.DEFAULT_CONFIG_PATH)


def governance_configured(path: str | Path | None = None) -> bool:
    """True once a tier2 config file exists (``neuralmind onboarding`` or any
    ``neuralmind team`` command that saved settings). Without one, nothing in
    the team-memory flow is gated or audited."""
    return _config_file(path).is_file()


def load_publish_policy(path: str | Path | None = None) -> PublishPolicy | None:
    """The publish policy to enforce, or None when there is nothing to enforce.

    None means governance was never configured or an admin disabled it
    (``team governance set-governance-enabled false``).

    Raises:
        ValueError: The config file holds an invalid governance value. Publish
            fails closed rather than silently publishing ungoverned memory.
    """
    path = _config_file(path)
    if not path.is_file():
        return None
    cfg = config_mod.load_config(path)
    if not cfg.governance.enabled:
        return None
    return PublishPolicy(
        scope=validate_scope(cfg.governance.publishing_scope),
        weight_threshold=float(cfg.governance.weight_threshold),
    )


def resolve_actor(project_path: str | Path | None = None) -> str:
    """Who to record in the audit log for a team-memory event.

    ``NEURALMIND_ACTOR_EMAIL`` / ``NEURALMIND_ACTOR`` first (same variables
    the ``team`` commands read), then the repository's ``git config
    user.email``, then the OS user.
    """
    env = (
        os.environ.get("NEURALMIND_ACTOR_EMAIL") or os.environ.get("NEURALMIND_ACTOR") or ""
    ).strip()
    if env:
        return env
    try:
        out = subprocess.run(
            ["git", "config", "user.email"],
            cwd=str(project_path) if project_path else None,
            capture_output=True,
            text=True,
            timeout=5,
        )
        if out.returncode == 0 and out.stdout.strip():
            return out.stdout.strip()
    except Exception:
        pass
    try:
        return f"{getpass.getuser()}@local"
    except Exception:
        return "unknown"


def record_team_event(
    action: str,
    target: str,
    details: dict[str, Any] | None = None,
    *,
    project_path: str | Path | None = None,
    actor: str | None = None,
    path: str | Path | None = None,
) -> bool | None:
    """Append a team-memory event (publish, import, review, removal) to the
    hash-chained audit log.

    Returns None when governance isn't configured (nothing is written), True
    once the entry is written, and False when the write failed — logged, never
    raised, so an audit hiccup can't break a session-start import.
    """
    path = _config_file(path)
    if not path.is_file():
        return None
    try:
        cfg = config_mod.load_config(path)
        AuditLog(Path(cfg.audit_db)).log(
            actor=actor or resolve_actor(project_path),
            action=action,  # type: ignore[arg-type]
            target=target,
            details=details or {},
        )
        return True
    except Exception:
        logger.warning("[governance] could not write %s audit entry for %s", action, target)
        return False
