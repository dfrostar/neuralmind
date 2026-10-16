"""Decision provenance — index the *why* behind code, not just the code.

NeuralMind remembers what a codebase *is*. It does not remember why it is that
way. When an agent asks "why is ``resolveOrgId`` per-handler instead of
middleware?", the answer — "avoids Prisma on /health, /metrics, /token; keeps
tests simple" — lives in a human's head or a scrolled-past chat, never in any
artifact the graph indexes. So every agent that touches that code re-derives,
re-asks, or worse, silently undoes the decision.

This module makes rationale a first-class, indexed memory. It reads a
``Decision:`` git trailer off commit messages — the cheapest possible capture
point, one the author already passes through — and turns it into a
:class:`DecisionRecord` keyed by the symbols it concerns, so recall can surface
it the moment those symbols light up.

    Decision: resolveOrgId is per-handler, not middleware — avoids Prisma on
              /health, /metrics, /token; keeps tests simple. Subjects:
              `resolveOrgId`, `authMiddleware`.

This is the most memory-anchored of the roadmap's features: it is not analysis,
it is remembering. The parser and recall operate on plain ``(sha, message)``
pairs, so they are testable with a list of tuples; git and the decision store
are reached only through :func:`harvest`, :func:`with_lifecycle` and
:func:`import_trailers` (the first and last take injectable git readers).

Lifecycle: a trailer can't be edited once committed, so its state lives in the
decision store (``neuralmind decisions``) under a stable id derived from the
rationale (:func:`trailer_decision_id`). ``neuralmind decisions scan`` (the
post-commit hook) imports each trailer there, naming the files its commit
changed; from then on ``decisions invalidate`` retracts it, ``decisions scan``
marks it STALE when a later commit changes those files, and ``restore`` brings
it back. :func:`with_lifecycle` applies that state before recall: INVALIDATED
decisions are dropped, STALE ones are shown with a warning.
"""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass, field, replace
from pathlib import Path

# The trailer token authors write. Git-trailer convention: "Token: value" at
# the end of a commit message, values may continue on indented lines.
TRAILER = "Decision"
SUBJECTS_TRAILER = "Subjects"

# Inline-code spans (`foo`) in the rationale are treated as subject hints even
# when no explicit Subjects: trailer is given — authors backtick the symbols
# they mean.
_BACKTICK = re.compile(r"`([^`]+)`")
_TRAILER_LINE = re.compile(rf"^{TRAILER}:\s*(.*)$", re.IGNORECASE)
_SUBJECTS_LINE = re.compile(rf"^{SUBJECTS_TRAILER}:\s*(.*)$", re.IGNORECASE)
_CONTINUATION = re.compile(r"^\s+(\S.*)$")


@dataclass(frozen=True)
class DecisionRecord:
    """One captured rationale, keyed by the symbols it concerns.

    ``subjects`` are the code identifiers the decision is *about* — the keys
    recall matches against. ``rationale`` is the one-sentence why. ``sha`` /
    ``short_sha`` point back at the commit so the agent can read the full
    context.
    """

    rationale: str
    subjects: tuple[str, ...] = field(default_factory=tuple)
    sha: str = ""
    # The decision store's status for this trailer (see with_lifecycle);
    # ACTIVE until the store says otherwise.
    status: str = "ACTIVE"

    @property
    def short_sha(self) -> str:
        return self.sha[:7] if self.sha else ""


def _extract_subjects(rationale: str, explicit: str | None) -> tuple[str, ...]:
    """Subjects from an explicit ``Subjects:`` trailer plus backticked spans.

    Explicit wins order; backticked hints in the rationale are appended. A
    subject is normalized to its bare symbol (drop a trailing ``()``) and
    de-duplicated, preserving first-seen order.
    """
    found: list[str] = []
    if explicit:
        found.extend(part.strip().strip("`") for part in explicit.split(","))
    found.extend(_BACKTICK.findall(rationale))
    seen: set[str] = set()
    out: list[str] = []
    for raw in found:
        sym = raw.strip().removesuffix("()").strip()
        if sym and sym.lower() not in seen:
            seen.add(sym.lower())
            out.append(sym)
    return tuple(out)


def parse_decision(message: str, sha: str = "") -> DecisionRecord | None:
    """Parse a ``Decision:`` trailer out of one commit message.

    Folds indented continuation lines into the rationale (standard git-trailer
    wrapping). Returns ``None`` when the message carries no decision — the
    common case — so callers can map over a whole log and filter falsy.
    Never raises on malformed input; a trailer with an empty value is treated
    as absent.
    """
    if not message:
        return None
    lines = message.splitlines()
    rationale_parts: list[str] = []
    explicit_subjects: str | None = None
    collecting = False

    for line in lines:
        m = _TRAILER_LINE.match(line)
        if m:
            collecting = True
            rationale_parts.append(m.group(1).strip())
            continue
        s = _SUBJECTS_LINE.match(line)
        if s:
            collecting = False
            explicit_subjects = s.group(1).strip()
            continue
        if collecting:
            cont = _CONTINUATION.match(line)
            if cont:
                rationale_parts.append(cont.group(1).strip())
            else:
                collecting = False

    rationale = " ".join(p for p in rationale_parts if p).strip()
    if not rationale:
        return None
    subjects = _extract_subjects(rationale, explicit_subjects)
    return DecisionRecord(rationale=rationale, subjects=subjects, sha=sha)


def parse_log(entries: list[tuple[str, str]]) -> list[DecisionRecord]:
    """Parse ``[(sha, message), ...]`` (git-log order) into decision records.

    Silently skips commits without a decision trailer. Preserves input order
    (newest-first if that is how the log was read).
    """
    out: list[DecisionRecord] = []
    for sha, message in entries:
        record = parse_decision(message, sha)
        if record is not None:
            out.append(record)
    return out


def _tokens(text: str) -> set[str]:
    return {t for t in re.split(r"[^A-Za-z0-9_]+", text.lower()) if len(t) > 2}


def recall(records: list[DecisionRecord], query: str, limit: int = 5) -> list[DecisionRecord]:
    """Return decisions whose subjects the query mentions, strongest first.

    A record matches when any of its subjects (or subject tokens) appears in
    the query — this is the "surface the rationale when its symbols light up"
    behavior the synapse graph will drive on recall. Ranked by number of
    subject hits. Empty when nothing matches.
    """
    q = _tokens(query)
    if not q:
        return []
    scored: list[tuple[int, int, DecisionRecord]] = []
    for idx, rec in enumerate(records):
        hits = 0
        for subject in rec.subjects:
            st = _tokens(subject)
            if subject.lower() in q or (st and st <= q):
                hits += 1
        if hits:
            # Sort by hits desc, then original order (stable, newest-first).
            scored.append((hits, -idx, rec))
    scored.sort(key=lambda x: (x[0], x[1]), reverse=True)
    return [rec for _, _, rec in scored[:limit]]


def format_decisions(records: list[DecisionRecord]) -> str:
    """Render recalled decisions as a markdown block for prompt injection.

    Empty string when there is nothing to surface, so callers can concatenate
    unconditionally.
    """
    if not records:
        return ""
    lines = ["## NeuralMind decision provenance", ""]
    for rec in records:
        subj = ", ".join(f"`{s}`" for s in rec.subjects) or "(unattributed)"
        ref = f" (see commit {rec.short_sha})" if rec.short_sha else ""
        stale = (
            " [STALE: its code changed after this was decided; check it still holds]"
            if rec.status == "STALE"
            else ""
        )
        lines.append(f"- {subj}: {rec.rationale}{ref}{stale}")
    return "\n".join(lines)


# --------------------------------------------------------------------------- #
# Lifecycle — the decision store holds each trailer's ACTIVE/STALE/INVALIDATED
# state, since the commit message itself can't change.
# --------------------------------------------------------------------------- #

# Fixed namespace for trailer ids. Never change it: every imported trailer's
# id in every project's decision store is derived from it.
_TRAILER_NAMESPACE = uuid.UUID("5d0c2f43-8a8e-4f55-9a0b-6c1e2b7d9f10")


def trailer_decision_id(record: DecisionRecord) -> str:
    """The decision-store id for a trailer decision.

    Derived from the rationale (whitespace and case folded), not the commit
    sha, so a rebase or cherry-pick that rewrites the commit keeps the same
    decision, and an invalidated one doesn't come back as new.
    """
    text = " ".join(record.rationale.split()).lower()
    return str(uuid.uuid5(_TRAILER_NAMESPACE, text))


def apply_lifecycle(
    records: list[DecisionRecord], statuses: dict[str, str]
) -> list[DecisionRecord]:
    """Drop INVALIDATED decisions and carry each other one's store status.

    ``statuses`` maps :func:`trailer_decision_id` to status; a trailer the
    store doesn't hold stays ACTIVE.
    """
    out: list[DecisionRecord] = []
    for rec in records:
        status = statuses.get(trailer_decision_id(rec), "ACTIVE")
        if status == "INVALIDATED":
            continue
        out.append(rec if status == rec.status else replace(rec, status=status))
    return out


def with_lifecycle(project_path: str, records: list[DecisionRecord]) -> list[DecisionRecord]:
    """:func:`apply_lifecycle` with the statuses in the project's decision store.

    Reads only: a project without a store gets ``records`` unchanged.
    """
    # Checked before importing the store module, which costs the prompt hook
    # ~0.1 s; most projects with trailers have no store.
    if not records or not (Path(project_path) / ".neuralmind" / "memory.db").is_file():
        return records
    from .memory.store import read_statuses

    ids = [trailer_decision_id(rec) for rec in records]
    return apply_lifecycle(records, read_statuses(project_path, ids))


# --------------------------------------------------------------------------- #
# Harvest — git history IS the store; the trailer is the persistence.
# --------------------------------------------------------------------------- #

# ASCII unit/record separators keep multi-line commit bodies unambiguous.
_GIT_FORMAT = "%H%x1f%B%x1e"


def read_git_log(project_path: str = ".", limit: int = 300) -> list[tuple[str, str]]:
    """Return ``[(sha, message), ...]`` for the last ``limit`` commits.

    Reads real git history via a subprocess — the only impure function in this
    module, kept separate so :func:`harvest` can be tested with a fake reader.
    Returns an empty list on any failure (not a git repo, git missing), so the
    whole feature fails open.
    """
    import subprocess

    try:
        # git writes commit messages as UTF-8; the locale default (cp1252 on
        # Windows) would garble a non-ASCII rationale, and with it the id
        # trailer_decision_id derives from it.
        out = subprocess.check_output(
            ["git", "-C", project_path, "log", f"-{int(limit)}", f"--format={_GIT_FORMAT}"],
            encoding="utf-8",
            errors="replace",
            stderr=subprocess.DEVNULL,
        )
    except Exception:
        return []
    entries: list[tuple[str, str]] = []
    for chunk in out.split("\x1e"):
        if "\x1f" in chunk:
            sha, message = chunk.split("\x1f", 1)
            entries.append((sha.strip(), message))
    return entries


def harvest(
    project_path: str = ".",
    limit: int = 300,
    log_reader=read_git_log,
) -> list[DecisionRecord]:
    """Harvest decision records from a project's recent git history.

    ``log_reader`` is injectable purely for testing; production passes the
    default git-backed reader. Fails open to an empty list.
    """
    try:
        entries = log_reader(project_path, limit)
    except Exception:
        return []
    return parse_log(entries)


def read_commit_files(project_path: str, sha: str) -> list[str]:
    """Files commit ``sha`` changed, relative to ``project_path`` (``[]`` on failure).

    The same diff ``decisions scan`` takes of HEAD: against the first parent,
    so a merge lists what it brought in; limited to the project directory; and
    NUL-separated, so no path comes back quoted. A trailer's files are then in
    exactly the form the scan matches.
    """
    from .memory.invalidate import get_changed_files

    return get_changed_files(project_path, sha)


def read_commit_blobs(project_path: str, files: list[str], sha: str) -> dict[str, str]:
    """``{path: git blob id}`` for ``files`` as commit ``sha`` stores them."""
    from .memory.invalidate import committed_blob_ids

    return committed_blob_ids(project_path, files, sha)


def _title(rationale: str, width: int = 80) -> str:
    """The rationale's first sentence, cut to ``width`` characters."""
    first = re.split(r"(?<=[.!?])\s", rationale, maxsplit=1)[0].strip()
    return first if len(first) <= width else first[: width - 1].rstrip() + "…"


def _shown(paths: list[str]) -> str:
    """Up to three paths, then a count, as ``decisions scan`` names them."""
    shown = ", ".join(paths[:3])
    return shown + (f" (+{len(paths) - 3} more)" if len(paths) > 3 else "")


def import_trailers(
    store,
    project_path: str,
    records: list[DecisionRecord],
    *,
    head: str = "",
    files_reader=read_commit_files,
    blobs_reader=read_commit_blobs,
) -> list[str]:
    """Bring trailer decisions into the decision store; return the ids newly recorded.

    A trailer the store doesn't hold is recorded under
    :func:`trailer_decision_id`, anchored to its commit, tagged ``trailer``,
    naming the files its commit changed, and fingerprinted with the blobs that
    commit stores, so it is judged against the code it described rather than
    today's working tree. If any of those files changed between its commit and
    ``head``, it is marked STALE straight away, with the files named.

    A trailer the store already holds is left alone, so importing again never
    revives an invalidated one. The exception is a trailer on ``head`` itself
    (an amended commit, or the same rationale committed again) that isn't
    INVALIDATED: it is re-anchored to ``head`` and made ACTIVE, so the commit
    that carries a decision never marks it STALE.

    Records are expected newest first (git-log order), so a rationale repeated
    in several commits is anchored to the newest.
    """
    imported: list[str] = []
    seen: set[str] = set()
    for rec in records:
        decision_id = trailer_decision_id(rec)
        if decision_id in seen or not rec.sha:
            continue
        seen.add(decision_id)
        existing = store.get(decision_id)
        if existing is None:
            files = files_reader(project_path, rec.sha)
            store.record(
                title=_title(rec.rationale),
                rationale=rec.rationale,
                commit_sha=rec.sha,
                files_affected=files,
                evidence=[f"Decision: trailer on commit {rec.short_sha}"],
                tags=["trailer"],
                id=decision_id,
            )
            if store.get(decision_id) is None:
                continue  # the write failed (logged by the store)
            at_commit = blobs_reader(project_path, files, rec.sha)
            store.set_fingerprints(decision_id, at_commit)
            imported.append(decision_id)
            if head and rec.sha != head:
                now = blobs_reader(project_path, files, head)
                changed = [f for f in files if now.get(f) != at_commit.get(f)]
                if changed:
                    store.mark_stale(
                        decision_id,
                        f"{_shown(changed)} changed after commit {rec.short_sha} "
                        "recorded this decision",
                    )
        elif rec.sha == head and existing.status != "INVALIDATED" and existing.commit_sha != head:
            files = files_reader(project_path, head)
            existing.commit_sha = head
            existing.files_affected = files
            existing.status = "ACTIVE"
            existing.evidence = [
                *existing.evidence,
                f"Re-anchored to commit {rec.short_sha}, which carries this trailer",
            ]
            store.update(existing)
            store.set_fingerprints(decision_id, blobs_reader(project_path, files, head))
    return imported
