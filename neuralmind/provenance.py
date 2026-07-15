"""Decision provenance — index the *why* behind code, not just the code (PROTOTYPE).

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
it is remembering. It operates on plain ``(sha, message)`` pairs, so it is
testable with a list of tuples and carries no git, SQLite, or embedder
dependency — the real caller feeds it ``git log`` output and stores the records
as decision nodes in the synapse graph.

Status: prototype. The parser and recall are complete and tested; wiring
``DecisionRecord`` into the synapse graph as a node kind, and harvesting on the
existing ``post-commit`` hook (``neuralmind init-hook``), is the promotion step.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

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
        lines.append(f"- {subj}: {rec.rationale}{ref}")
    return "\n".join(lines)
