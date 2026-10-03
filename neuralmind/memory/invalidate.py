"""Invalidation Engine — Git-aware staleness detection for DecisionRecords.

Conservative invalidation: when a commit changes a file named in a decision's
``files_affected``, the decision is marked STALE — there is no diff analysis,
any change counts. Better to lose a valid memory than serve a stale one.

The one exemption is the commit that *carries* the decision. When a decision
is recorded, amended or restored, the store fingerprints each affected file
(its git blob id, exactly as ``git add`` would store it). If the commit
contains exactly those blobs for every changed file the decision names, it
carries the code the decision describes, so it leaves the decision ACTIVE.
In practice: edit ``auth.py``, record why, commit — the decision survives,
however quickly the three steps follow each other; edit ``auth.py`` again
before or after committing and it goes STALE. No fingerprint (an older
record, a file that didn't exist yet, no git) means no exemption.

Lifecycle:
    1. ``neuralmind decisions scan`` runs ``scan()``; the post-commit hook
       installed by ``neuralmind init-hook`` calls it after every commit.
    2. It lists the files the HEAD commit changed relative to its first
       parent (so a merge commit counts everything it brought in, and a
       rename counts both paths), relative to the project directory.
    3. It asks the DecisionStore for decisions naming any of those files —
       by project-relative or absolute path.
    4. Each match that isn't exempt (above) is marked STALE, with the reason
       recorded on the decision when the store supports it (``mark_stale``).
    5. Cascading: decisions that depend on a newly stale one go STALE too.
    6. An event is published on the process event bus for each invalidation.

The DecisionStore interface expected by this module::

    class DecisionStore:
        def find_by_files(self, files: list[str]) -> list[DecisionRecord]:
            ...  # Return decisions where files_affected overlap

        def find_dependents(self, decision_id: str) -> list[DecisionRecord]:
            ...  # Return decisions where decision_id in dependency_constraints

        def update_status(self, decision_id: str, status: str) -> None:
            ...  # Persist status change

        # Optional: mark_stale(decision_id, reason) -> bool records the
        # reason and reports whether the status was persisted;
        # fingerprints(decision_id) -> {path: blob id} enables the
        # carried-by-this-commit exemption.

Each DecisionRecord needs ``id``, ``status``, ``commit_sha``,
``files_affected`` and ``dependency_constraints``. Without ``fingerprints``
every touched decision goes STALE.
"""

from __future__ import annotations

import logging
import subprocess
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
from typing import Any, Protocol

logger = logging.getLogger(__name__)

# Paths per find_by_files() call — under SQLite's legacy 999-parameter limit.
_LOOKUP_CHUNK = 900

# Paths per git hash-object / ls-tree call, to stay under OS argv limits.
_GIT_PATH_CHUNK = 200


# --------------------------------------------------------------------------- #
# Protocol: what the engine needs from a decision store
# --------------------------------------------------------------------------- #


class DecisionRecord(Protocol):
    """Structural type for a decision record — duck-typed for flexibility.

    The engine never instantiates these; it only reads them from the store.
    ``neuralmind.memory.store.DecisionRecord`` is the production shape.
    """

    id: str
    commit_sha: str
    files_affected: list[str]
    dependency_constraints: list[str]
    status: str  # "ACTIVE" | "STALE" | "INVALIDATED"


class DecisionStore(Protocol):
    """The minimal interface the InvalidationEngine needs from a store.

    Backed by SQLite in production (``neuralmind.memory.store.DecisionStore``).
    In tests, a dict-backed mock works fine.
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


def get_parent_commit(project_path: str | Path) -> str:
    """SHA of HEAD's first parent, or "" for a root commit / non-repo."""
    result = _git(["rev-parse", "--verify", "--quiet", "HEAD^"], cwd=project_path)
    if result.returncode != 0:
        return ""
    return result.stdout.strip()


def get_changed_files(project_path: str | Path) -> list[str]:
    """Files the HEAD commit changed, relative to ``project_path``.

    Diffs HEAD against its first parent, so a merge commit lists everything
    it brought into the branch; ``--no-renames`` lists both sides of a rename
    so a decision about the old path is found too. Paths are relative to
    ``project_path`` (``--relative``) and changes outside it are left out, so
    a project in a subdirectory of its repository matches its own decisions.
    A root commit lists every file it added. Returns [] outside a git repo.
    """
    parent = get_parent_commit(project_path)
    if parent:
        args = ["diff", "--name-only", "--relative", "--no-renames", "-z", parent, "HEAD"]
    else:
        args = [
            "diff-tree",
            "--no-commit-id",
            "--name-only",
            "-r",
            "--root",
            "--relative",
            "--no-renames",
            "-z",
            "HEAD",
        ]
    result = _git(args, cwd=project_path)
    if result.returncode != 0:
        return []
    return [p for p in result.stdout.split("\0") if p.strip()]


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


def _project_relative(path: str, root: Path) -> str:
    """A decision's file path in the form ``get_changed_files`` reports."""
    text = str(path).replace("\\", "/")
    candidate = Path(text)
    if candidate.is_absolute():
        try:
            return candidate.resolve().relative_to(root).as_posix()
        except (ValueError, OSError):
            return text
    return PurePosixPath(text).as_posix()


def file_blob_ids(project_path: str | Path, files: list[str]) -> dict[str, str]:
    """``{project-relative path: git blob id}`` for the files as they are now.

    Uses ``git hash-object``, which applies the same clean filters and
    line-ending normalization as ``git add``, so the ids compare equal to what
    a commit stores. Files that don't exist are left out; any git failure
    returns what was hashed so far (possibly nothing).
    """
    root = Path(project_path).resolve()
    existing: list[str] = []
    for path in files or []:
        rel = _project_relative(path, root)
        if rel not in existing and (root / rel).is_file():
            existing.append(rel)
    blobs: dict[str, str] = {}
    for start in range(0, len(existing), _GIT_PATH_CHUNK):
        chunk = existing[start : start + _GIT_PATH_CHUNK]
        result = _git(["hash-object", "--", *chunk], cwd=root)
        ids = result.stdout.split()
        if result.returncode != 0 or len(ids) != len(chunk):
            break
        blobs.update(zip(chunk, ids, strict=True))
    return blobs


def committed_blob_ids(project_path: str | Path, files: list[str]) -> dict[str, str]:
    """``{project-relative path: git blob id}`` of the files as HEAD stores them.

    Files HEAD doesn't contain (deleted, or the old side of a rename) are
    left out, which makes them count as changed.
    """
    blobs: dict[str, str] = {}
    paths = list(dict.fromkeys(files or []))
    for start in range(0, len(paths), _GIT_PATH_CHUNK):
        chunk = paths[start : start + _GIT_PATH_CHUNK]
        result = _git(["ls-tree", "-z", "HEAD", "--", *chunk], cwd=project_path)
        if result.returncode != 0:
            continue
        for record in result.stdout.split("\0"):
            meta, _, path = record.partition("\t")
            parts = meta.split()
            if len(parts) == 3 and parts[1] == "blob" and path:
                blobs[path] = parts[2]
    return blobs


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

    Conservative: invalidates on ANY change to a decision's files — no diff
    analysis — except in the commit that carries the decision (see the
    module docstring).

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
        """Mark STALE the decisions whose files the HEAD commit changed.

        Returns the list of newly-invalidated decision IDs (cascaded
        dependents included). Idempotent — already-stale decisions are
        not re-invalidated.
        """
        self._last_events.clear()

        if not is_git_repo(self.project_path):
            logger.debug("[invalidate] not a git repo, skipping scan")
            return []

        changed_files = get_changed_files(self.project_path)
        if not changed_files:
            logger.debug("[invalidate] no files changed in HEAD")
            return []

        head = get_current_commit(self.project_path)
        root = Path(self.project_path).resolve()
        changed = set(changed_files)
        logger.info(
            "[invalidate] scanning %d changed file(s) at %s",
            len(changed_files),
            head[:7] or "?",
        )

        committed: dict[str, str] | None = None  # HEAD's blob ids, fetched on first need
        newly_invalidated: list[str] = []
        for decision in self._decisions_naming(changed_files, root):
            if decision.status in ("STALE", "INVALIDATED"):
                continue
            if head and getattr(decision, "commit_sha", "") == head:
                continue  # recorded against this very commit
            touched = self._touched_files(decision, changed, root)
            if not touched:
                continue
            if committed is None:
                committed = committed_blob_ids(self.project_path, changed_files)
            if self._carried_by_commit(decision, touched, committed):
                continue
            shown = ", ".join(touched[:3])
            if len(touched) > 3:
                shown += f" (+{len(touched) - 3} more)"
            reason = f"commit {head[:7] or '?'} changed {shown} since this decision was recorded"
            if self.invalidate_decision(
                decision.id,
                reason=reason,
                triggered_by="file_change",
                commit_sha=head,
                files=touched,
            ):
                newly_invalidated.append(decision.id)

        for decision_id in list(newly_invalidated):
            newly_invalidated.extend(self.cascade_invalidation(decision_id, commit_sha=head))

        return list(dict.fromkeys(newly_invalidated))  # Preserve order, dedupe

    def invalidate_decision(
        self,
        decision_id: str,
        reason: str = "",
        *,
        triggered_by: str = "file_change",
        commit_sha: str | None = None,
        files: list[str] | None = None,
    ) -> bool:
        """Mark a single decision as STALE; True once the store has it.

        Uses the store's ``mark_stale`` when it has one, so the reason is kept
        on the decision itself; otherwise ``update_status``. A store that
        reports the write failed (``mark_stale`` returning False) gets no
        event and the decision isn't reported as stale — it is still ACTIVE.
        Publishes an event on the process event bus.
        """
        mark_stale = getattr(self.store, "mark_stale", None)
        if callable(mark_stale):
            persisted = mark_stale(decision_id, reason)
        else:
            persisted = self.store.update_status(decision_id, "STALE")
        if persisted is False:
            logger.warning(
                "[invalidate] could not mark decision %s STALE; leaving it unreported", decision_id
            )
            return False
        event = InvalidationEvent(
            decision_id=decision_id,
            reason=reason,
            triggered_by=triggered_by,
            commit_sha=(
                commit_sha if commit_sha is not None else get_current_commit(self.project_path)
            ),
            files=list(files or []),
        )
        self._last_events.append(event)
        self._emit_audit_event(event)
        logger.info("[invalidate] decision %s marked STALE: %s", decision_id, reason)
        return True

    def cascade_invalidation(self, decision_id: str, commit_sha: str | None = None) -> list[str]:
        """For a stale decision, find and invalidate its dependents.

        A dependent is a decision whose ``dependency_constraints`` includes
        the stale decision's id. Those dependents are now questionable —
        their reasoning was based on the stale decision.

        Returns the list of newly-invalidated dependent IDs.
        """
        dependents = self.store.find_dependents(decision_id)
        invalidated: list[str] = []

        for dep in dependents:
            if dep.status in ("STALE", "INVALIDATED"):
                continue
            reason = f"depends on stale decision {decision_id}"
            if not self.invalidate_decision(
                dep.id, reason=reason, triggered_by="cascade", commit_sha=commit_sha
            ):
                continue
            invalidated.append(dep.id)

            # Recursive cascade: dependents of dependents
            nested = self.cascade_invalidation(dep.id, commit_sha=commit_sha)
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

    def _decisions_naming(self, changed_files: list[str], root: Path) -> list[DecisionRecord]:
        """Decisions whose files include any changed file, each listed once.

        Decisions may name a file project-relative or by absolute path (with
        or without symlinks resolved), so every form is looked up — in chunks,
        to stay under SQLite's bound-parameter limit on very large commits.
        """
        bases = dict.fromkeys((root, Path(self.project_path).absolute()))
        forms = list(changed_files) + [(b / f).as_posix() for b in bases for f in changed_files]
        lookup = list(dict.fromkeys(forms))
        found: dict[str, DecisionRecord] = {}
        for start in range(0, len(lookup), _LOOKUP_CHUNK):
            for decision in self.store.find_by_files(lookup[start : start + _LOOKUP_CHUNK]):
                found.setdefault(decision.id, decision)
        return list(found.values())

    @staticmethod
    def _touched_files(decision: DecisionRecord, changed: set[str], root: Path) -> list[str]:
        """The decision's files that the commit changed, project-relative."""
        touched: list[str] = []
        for path in decision.files_affected or []:
            rel = _project_relative(path, root)
            if rel in changed and rel not in touched:
                touched.append(rel)
        return touched

    def _carried_by_commit(
        self, decision: DecisionRecord, touched: list[str], committed: dict[str, str]
    ) -> bool:
        """True when the commit contains exactly what the decision saw.

        Every changed file the decision names must have a fingerprint (its
        blob id when the decision was recorded, amended or restored) equal to
        the blob HEAD stores. Then this commit carries the code the decision
        describes. A store without fingerprints, a missing fingerprint, or a
        file HEAD no longer contains is never exempt.
        """
        fingerprints = getattr(self.store, "fingerprints", None)
        if not callable(fingerprints):
            return False
        try:
            recorded = fingerprints(decision.id) or {}
        except Exception:
            return False
        return all(
            recorded.get(rel) is not None and recorded.get(rel) == committed.get(rel)
            for rel in touched
        )

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
            logger.debug(
                "[memory] event bus publish failed for %s (non-blocking)", event.decision_id
            )


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
