"""Invalidation Engine — Git-aware staleness detection for DecisionRecords.

Conservative invalidation: any file touch that affects a decision's
``files_affected`` marks it STALE. Better to lose a valid memory than
serve a stale one.

Lifecycle:
    1. ``scan()`` runs on each git commit (post-commit hook) or on
       demand (pre-compact hook, context selection time).
    2. It queries the DecisionStore for decisions whose files_affected
       overlap with the files changed in HEAD.
    3. Each matching decision is marked STALE (status = "STALE").
    4. Cascading: dependents of stale decisions are flagged too.
    5. An audit event is emitted for each invalidation.

The DecisionStore interface expected by this module::

    class DecisionStore:
        def find_by_files(self, files: list[str]) -> list[DecisionRecord]:
            ...  # Return decisions where files_affected overlap

        def find_dependents(self, decision_id: str) -> list[DecisionRecord]:
            ...  # Return decisions where decision_id in dependency_constraints

        def update_status(self, decision_id: str, status: str) -> None:
            ...  # Persist status change

Each DecisionRecord must have::

    @dataclass
    class DecisionRecord:
        id: str                          # Unique decision identifier
        rationale: str                   # The "why"
        subjects: tuple[str, ...]        # Code symbols concerned
        sha: str                         # Commit where decision was made
        files_affected: list[str]        # Files this decision concerns
        dependency_constraints: list[str] # Decision IDs this depends on
        status: str = "VALID"            # VALID | STALE
"""

from __future__ import annotations

import logging
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol

logger = logging.getLogger(__name__)


# --------------------------------------------------------------------------- #
# Protocol: what the engine needs from a decision store
# --------------------------------------------------------------------------- #


class DecisionRecord(Protocol):
    """Structural type for a decision record — duck-typed for flexibility.

    The engine never instantiates these; it only reads them from the store.
    Matches the shape of ``neuralmind.provenance.DecisionRecord`` plus the
    additional fields the invalidation layer needs.
    """

    id: str
    rationale: str
    subjects: tuple[str, ...]
    sha: str
    files_affected: list[str]
    dependency_constraints: list[str]
    status: str  # "VALID" | "STALE"


class DecisionStore(Protocol):
    """The minimal interface the InvalidationEngine needs from a store.

    Backed by SQLite in production (synapses.py's SynapseStore, or a
    dedicated decisions table). In tests, a dict-backed mock works fine.
    """

    def find_by_files(self, files: list[str]) -> list[DecisionRecord]:
        """Return decisions whose files_affected overlap the given paths."""

    def find_dependents(self, decision_id: str) -> list[DecisionRecord]:
        """Return decisions that depend on the given decision_id."""

    def update_status(self, decision_id: str, status: str) -> None:
        """Persist a status change."""


# --------------------------------------------------------------------------- #
# Git integration helpers
# --------------------------------------------------------------------------- #


def _git(
    args: list[str],
    cwd: str | Path,
    *,
    check: bool = False,
) -> subprocess.CompletedProcess[str]:
    """Run a git subprocess with consistent error handling.

    Returns a CompletedProcess with empty stdout on any failure —
    never raises unless ``check=True`` is explicitly requested.
    """
    try:
        return subprocess.run(
            ["git", "-C", str(cwd)] + args,
            capture_output=True,
            text=True,
            check=check,
            timeout=30,
        )
    except subprocess.TimeoutExpired:
        logger.warning("[invalidate] git %s timed out", args[0] if args else "?")
        return subprocess.CompletedProcess(args, returncode=1, stdout="", stderr="timeout")
    except FileNotFoundError:
        logger.warning("[invalidate] git not found on PATH")
        return subprocess.CompletedProcess(args, returncode=127, stdout="", stderr="git not found")
    except Exception as e:
        logger.warning("[invalidate] git %s failed: %s", args[0] if args else "?", e)
        return subprocess.CompletedProcess(args, returncode=1, stdout="", stderr=str(e))


def get_changed_files(project_path: str | Path) -> list[str]:
    """Get files changed in HEAD commit.

    Uses ``git diff-tree --no-commit-id --name-only -r HEAD``.
    Returns empty list if not a git repo or git is unavailable.
    """
    result = _git(
        ["diff-tree", "--no-commit-id", "--name-only", "-r", "HEAD"],
        cwd=project_path,
    )
    if result.returncode != 0:
        return []
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def get_current_commit(project_path: str | Path) -> str:
    """Get current HEAD SHA.

    Returns empty string if not a git repo or git is unavailable.
    """
    result = _git(["rev-parse", "HEAD"], cwd=project_path)
    if result.returncode != 0:
        return ""
    return result.stdout.strip()


def is_git_repo(project_path: str | Path) -> bool:
    """Check if path is inside a git repository."""
    result = _git(["rev-parse", "--git-dir"], cwd=project_path)
    return result.returncode == 0


def is_file_changed(file_path: str, since_commit: str, project_path: str | Path) -> bool:
    """Check if a file has changed since a specific git commit.

    Uses ``git diff --quiet`` to check if the file differs between
    the given commit and HEAD/working tree. Conservative: if the file
    doesn't exist or git fails, returns True (assume changed).
    """
    full_path = Path(project_path) / file_path
    if not full_path.exists():
        logger.debug("[invalidate] file %s does not exist, treating as changed", file_path)
        return True

    result = _git(
        ["diff", "--quiet", since_commit, "--", file_path],
        cwd=project_path,
    )
    if result.returncode == 0:
        # No diff → file unchanged
        return False
    if result.returncode == 1:
        # Diff exists → file changed
        return True
    # Error (e.g., invalid commit) — conservative: assume changed
    logger.warning(
        "[invalidate] git diff --quiet returned %d for %s, treating as changed",
        result.returncode,
        file_path,
    )
    return True


# --------------------------------------------------------------------------- #
# Invalidation Engine
# --------------------------------------------------------------------------- #


@dataclass
class InvalidationEvent:
    """An audit record emitted for each invalidation decision."""

    decision_id: str
    reason: str
    triggered_by: str  # "file_change" or "cascade"
    commit_sha: str = ""
    files: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": "decision_invalidated",
            "decision_id": self.decision_id,
            "reason": self.reason,
            "triggered_by": self.triggered_by,
            "commit_sha": self.commit_sha,
            "files": self.files,
        }


class InvalidationEngine:
    """Git-aware decision invalidation engine.

    Conservative: invalidates on ANY file touch — no diff analysis.
    Better to lose a valid memory than serve a stale one.

    Usage::

        engine = InvalidationEngine("/path/to/project", store)
        newly_stale = engine.scan()  # Returns list of invalidated IDs

    The engine is idempotent: running scan() multiple times will not
    re-invalidate already-stale decisions.
    """

    def __init__(self, project_path: str, store: DecisionStore) -> None:
        self.project_path = str(project_path)
        self.store = store
        self._last_events: list[InvalidationEvent] = []

    # ------------------------------------------------------------------- #
    # Public API
    # ------------------------------------------------------------------- #

    def scan(self) -> list[str]:
        """Full invalidation scan: find changed files, mark stale, cascade.

        Returns the list of newly-invalidated decision IDs. Idempotent —
        already-stale decisions are not re-invalidated.
        """
        self._last_events.clear()

        if not is_git_repo(self.project_path):
            logger.debug("[invalidate] not a git repo, skipping scan")
            return []

        changed_files = get_changed_files(self.project_path)
        if not changed_files:
            logger.debug("[invalidate] no files changed in HEAD")
            return []

        current_sha = get_current_commit(self.project_path)
        logger.info(
            "[invalidate] scanning %d changed file(s) at %s",
            len(changed_files),
            current_sha[:7] or "?",
        )

        # Step 1: Find decisions referencing changed files
        candidates = self.store.find_by_files(changed_files)

        # Step 2: Mark stale
        newly_invalidated: list[str] = []
        for decision in candidates:
            if decision.status == "STALE":
                continue  # Already invalidated

            # Conservative: if commit_sha differs from HEAD, the decision
            # was made at a different state of the codebase.
            if decision.commit_sha and current_sha and decision.commit_sha != current_sha:
                reason = f"commit mismatch (decision at {decision.commit_sha[:7]}, HEAD is {current_sha[:7]})"
                self.invalidate_decision(decision.id, reason=reason, triggered_by="commit_mismatch")
                newly_invalidated.append(decision.id)
                continue

            # Primary path: files were touched
            reason = f"files affected changed: {', '.join(decision.files_affected[:3])}"
            if len(decision.files_affected) > 3:
                reason += f" (+{len(decision.files_affected) - 3} more)"
            self.invalidate_decision(decision.id, reason=reason, triggered_by="file_change")
            newly_invalidated.append(decision.id)

        # Step 3: Cascade to dependents
        for decision_id in newly_invalidated:
            cascade_ids = self.cascade_invalidation(decision_id)
            newly_invalidated.extend(cascade_ids)

        return list(dict.fromkeys(newly_invalidated))  # Preserve order, dedupe

    def invalidate_decision(
        self,
        decision_id: str,
        reason: str = "",
        *,
        triggered_by: str = "file_change",
    ) -> None:
        """Mark a single decision as STALE.

        Emits an audit event via the event bus (if available) and updates
        the store.
        """
        self.store.update_status(decision_id, "STALE")
        event = InvalidationEvent(
            decision_id=decision_id,
            reason=reason,
            triggered_by=triggered_by,
            commit_sha=get_current_commit(self.project_path),
        )
        self._last_events.append(event)
        self._emit_audit_event(event)
        logger.info("[invalidate] decision %s marked STALE: %s", decision_id, reason)

    def cascade_invalidation(self, decision_id: str) -> list[str]:
        """For a stale decision, find and invalidate its dependents.

        A dependent is a decision whose ``dependency_constraints`` includes
        the stale decision's id. Those dependents are now questionable —
        their reasoning was based on the stale decision.

        Returns the list of newly-invalidated dependent IDs.
        """
        dependents = self.store.find_dependents(decision_id)
        invalidated: list[str] = []

        for dep in dependents:
            if dep.status == "STALE":
                continue
            reason = f"depends on stale decision {decision_id}"
            self.invalidate_decision(dep.id, reason=reason, triggered_by="cascade")
            invalidated.append(dep.id)

            # Recursive cascade: dependents of dependents
            nested = self.cascade_invalidation(dep.id)
            invalidated.extend(nested)

        return list(dict.fromkeys(invalidated))

    def get_stale(self) -> list[DecisionRecord]:
        """Return all currently-stale decisions from the store.

        The engine itself does not cache state — it delegates to the store.
        This method is a convenience wrapper that returns decisions whose
        status is "STALE".
        """
        # The store exposes find_by_files; for stale detection we need
        # a different query. We rely on the store having a find_stale method
        # and fall back to empty if not implemented.
        if hasattr(self.store, "find_stale"):
            return self.store.find_stale()  # type: ignore[attr-defined]
        logger.warning("[invalidate] store has no find_stale(); cannot enumerate stale decisions")
        return []

    def is_file_changed(self, file_path: str, since_commit: str) -> bool:
        """Check if a file has changed since a specific git commit.

        Delegates to the module-level helper. Included as an instance
        method for API symmetry with the TRD spec.
        """
        return is_file_changed(file_path, since_commit, self.project_path)

    @property
    def last_events(self) -> list[InvalidationEvent]:
        """Events emitted during the most recent scan/invalidate call."""
        return list(self._last_events)

    # ------------------------------------------------------------------- #
    # Internal
    # ------------------------------------------------------------------- #

    def _emit_audit_event(self, event: InvalidationEvent) -> None:
        """Publish an invalidation event on the process-wide event bus.

        Best-effort: failures are swallowed so invalidation never breaks
        due to event bus issues.
        """
        try:
            from ..event_bus import publish

            publish("decision_invalidated", event.to_dict())
        except Exception:
            # Event bus is optional — log at DEBUG so normal operation is
            # silent, but misconfigured event routing is diagnosable.
            logger.debug("[memory] event bus publish failed for %s (non-blocking)", event.id)


# --------------------------------------------------------------------------- #
# Simple in-memory store (for tests / standalone use)
# --------------------------------------------------------------------------- #


class InMemoryDecisionStore:
    """A dict-backed DecisionStore for testing and standalone use.

    Not thread-safe. Suitable for single-threaded tests or as a
    reference implementation of the DecisionStore protocol.
    """

    def __init__(self) -> None:
        self._records: dict[str, DecisionRecord] = {}

    def add(self, record: DecisionRecord) -> None:
        """Add a decision record to the store."""
        self._records[record.id] = record

    def find_by_files(self, files: list[str]) -> list[DecisionRecord]:
        """Return decisions whose files_affected overlap the given paths."""
        file_set = set(files)
        return [rec for rec in self._records.values() if set(rec.files_affected) & file_set]

    def find_dependents(self, decision_id: str) -> list[DecisionRecord]:
        """Return decisions that depend on the given decision_id."""
        return [rec for rec in self._records.values() if decision_id in rec.dependency_constraints]

    def find_stale(self) -> list[DecisionRecord]:
        """Return all decisions with status STALE."""
        return [rec for rec in self._records.values() if rec.status == "STALE"]

    def update_status(self, decision_id: str, status: str) -> None:
        """Update a decision's status.

        Note: DecisionRecord is a Protocol / frozen dataclass, so we
        replace the record in the store. The caller should expect the
        record object to be replaced.
        """
        rec = self._records.get(decision_id)
        if rec is None:
            return
        # Use object.__setattr__ to bypass frozen dataclass restriction
        # on records that are @dataclass(frozen=True).
        try:
            rec.status = status  # type: ignore[misc]
        except AttributeError:
            # Frozen dataclass — replace the record
            new_rec = _replace_field(rec, "status", status)
            self._records[decision_id] = new_rec


def _replace_field(record: DecisionRecord, field_name: str, value: Any) -> DecisionRecord:
    """Create a shallow copy of a decision record with one field replaced.

    Works with both frozen and mutable dataclasses.
    """
    import copy

    new_record = copy.copy(record)
    object.__setattr__(new_record, field_name, value)
    return new_record
