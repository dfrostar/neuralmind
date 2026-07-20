"""Team memory — a committed, auto-inherited bundle of learned associations.

The synapse layer learns *what code goes with what* from how a developer works.
This module makes that learned signal a **team artifact**: a project commits one
portable bundle, and every teammate's agent inherits it automatically on the
next session/build — so a fresh ``git clone`` starts with the team's earned
intuition instead of relearning it from scratch.

Design (PRD ``docs/prd/team-memory.md``):

- **Committed path** — ``<project>/.neuralmind-team-memory.json`` at the repo
  root (NOT under the per-machine, git-ignored ``.neuralmind/`` directory, so it
  commits normally with no ``.gitignore`` negation needed).
- **`publish_team_memory`** — export the union of the ``personal`` + ``shared``
  namespaces (MAX-merged), provenance-stamped, to the committed path.
- **`maybe_import_team_memory`** — if the committed bundle's content hash hasn't
  been imported yet (tracked in the store's ``meta`` table), merge it once into
  the ``shared`` namespace. Idempotent, fail-open, gated by
  ``NEURALMIND_TEAM_MEMORY=0``. Wired into the ``SessionStart`` hook and
  ``neuralmind build`` so inheritance is zero-effort.

Imports stay MAX-merge (a bundle can only *raise* the weight of pairs it
asserts) and the ``shared`` namespace decays, so a stale/over-eager bundle can't
permanently distort recall — and it only ever writes ``shared`` (never the
developer's ``personal`` or branch memory).
"""

from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .contribution_scoring import ContributionQualityScorer
from .ir import (
    SYNAPSE_BUNDLE_FORMAT,
    SYNAPSE_BUNDLE_KIND_TRANSITION,
    SYNAPSE_BUNDLE_VERSION,
    export_synapse_bundle,
)
from .merge_semantics import QualityWeightedMerger
from .peer_review import PeerReviewGate
from .synapses import DEFAULT_NAMESPACE, SHARED_NAMESPACE

# Committed at the repo root, beside .gitignore — NOT inside the git-ignored
# .neuralmind/ state dir, so it travels with `git clone` with no gitignore hack.
TEAM_BUNDLE_FILENAME = ".neuralmind-team-memory.json"

# Store ``meta`` key recording the content hash of the last team bundle imported
# into ``shared`` — the idempotency gate so we import each bundle exactly once.
_META_TEAM_HASH = "team_bundle_imported_hash"

# Store ``meta`` key for the pending review queue — edges that need operator
# approval before entering ``shared``. Value is a JSON list of dicts with
# source, target, score, reason, reviewer_hint.
_META_PENDING_REVIEW = "team_pending_review"

# Keep the committed file compact: cap each list to the strongest associations.
_TEAM_BUNDLE_CAP = 5000


def _load_pending_review(store: Any) -> list[dict]:
    """Load the pending review queue from the store's meta table."""
    try:
        raw = store.get_meta(_META_PENDING_REVIEW)
        if raw:
            return json.loads(raw)
    except Exception:
        pass
    return []


def _save_pending_review(store: Any, queue: list[dict]) -> None:
    """Persist the pending review queue to the store's meta table."""
    try:
        store.set_meta(_META_PENDING_REVIEW, json.dumps(queue))
    except Exception:
        pass


def _add_to_pending_review(store: Any, decision: Any) -> None:
    """Add a review decision to the pending review queue."""
    queue = _load_pending_review(store)
    queue.append({
        "source": decision.edge.source,
        "target": decision.edge.target,
        "score": round(decision.edge.score, 4),
        "reason": decision.reason,
        "reviewer_hint": decision.reviewer_hint,
    })
    _save_pending_review(store, queue)


def team_bundle_path(project_path: str | Path) -> Path:
    """Path to the committed team-memory bundle for ``project_path``."""
    return Path(project_path) / TEAM_BUNDLE_FILENAME


def _content_hash(bundle: dict[str, Any]) -> str:
    """Stable hash of a bundle's *learned content* (ignores timestamps/provenance).

    Two publishes of the same associations hash identically, so re-importing is
    a no-op even if the provenance header differs."""
    rows: list[tuple] = []
    for e in bundle.get("synapses", []):
        rows.append(("S", e["source"], e["target"], round(float(e.get("weight", 0.0)), 6)))
    for e in bundle.get("transitions", []):
        rows.append(("T", e["source"], e["target"], round(float(e.get("weight", 0.0)), 6)))
    rows.sort()
    return hashlib.sha256(json.dumps(rows, separators=(",", ":")).encode("utf-8")).hexdigest()


def build_team_bundle(store: Any) -> dict[str, Any]:
    """Build a portable team bundle from the union of ``personal`` + ``shared``.

    Each ``(source, target)`` pair keeps the MAX of *each* field — weight and
    activation_count/count merge independently — across the two source
    namespaces; entries are sorted strongest-first and capped so the committed
    file stays small. The bundle imports into ``shared`` by default.
    """

    def _merge(into: dict[tuple[str, str], dict], e: dict, count_field: str) -> None:
        # Merge per-field maxima, not whole entries: keeping the higher-weight
        # entry wholesale could drop a larger activation_count/count from the
        # other namespace. Since import also MAX-merges count, that would weaken
        # post-import LTP/decay relative to what the developer actually learned.
        key = (e["source"], e["target"])
        cur = into.get(key)
        if cur is None:
            into[key] = dict(e)
            return
        if float(e.get("weight", 0.0)) > float(cur.get("weight", 0.0)):
            cur["weight"] = e.get("weight", 0.0)
        if int(e.get(count_field, 0)) > int(cur.get(count_field, 0)):
            cur[count_field] = e.get(count_field, 0)

    syn: dict[tuple[str, str], dict] = {}
    tr: dict[tuple[str, str], dict] = {}
    for ns in (DEFAULT_NAMESPACE, SHARED_NAMESPACE):
        part = export_synapse_bundle(store, ns)
        for e in part.get("synapses", []):
            _merge(syn, e, "activation_count")
        for e in part.get("transitions", []):
            _merge(tr, e, "count")

    def _top(entries: dict[tuple[str, str], dict]) -> list[dict]:
        ordered = sorted(
            entries.values(),
            key=lambda e: (-float(e.get("weight", 0.0)), e["source"], e["target"]),
        )
        return ordered[:_TEAM_BUNDLE_CAP]

    synapses = _top(syn)
    transitions = _top(tr)
    bundle: dict[str, Any] = {
        "format": SYNAPSE_BUNDLE_FORMAT,
        "version": SYNAPSE_BUNDLE_VERSION,
        # Import target: shared, so a teammate's `personal`/branch memory is
        # never overwritten by an inherited bundle.
        "namespace": SHARED_NAMESPACE,
        "synapses": synapses,
        "transitions": transitions,
        "counts": {"synapses": len(synapses), "transitions": len(transitions)},
    }
    from . import __version__  # lazy: avoids a circular import at package load

    bundle["content_hash"] = _content_hash(bundle)
    bundle["provenance"] = {
        "tool": "neuralmind",
        "tool_version": __version__,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "source_namespaces": [DEFAULT_NAMESPACE, SHARED_NAMESPACE],
    }
    return bundle


def publish_team_memory(project_path: str | Path, store: Any) -> dict[str, Any]:
    """Write the project's learned memory to the committed team-bundle path.

    Returns a summary ``{path, counts, content_hash}``. Records the published
    hash in the store so we don't re-import what we just published.
    """
    bundle = build_team_bundle(store)
    path = team_bundle_path(project_path)
    path.write_text(json.dumps(bundle, indent=2) + "\n", encoding="utf-8")
    try:
        store.set_meta(_META_TEAM_HASH, bundle["content_hash"])
    except Exception:
        pass
    return {
        "path": str(path),
        "counts": bundle["counts"],
        "content_hash": bundle["content_hash"],
    }


def maybe_import_team_memory(project_path: str | Path, store: Any) -> dict[str, Any] | None:
    """Import the committed team bundle into ``shared`` once, if present and new.

    Returns the import summary on a fresh import, or ``None`` when there's
    nothing to do (no bundle, already imported, disabled, or unreadable). Never
    raises — inheritance must never break a session or a build.
    """
    if os.environ.get("NEURALMIND_TEAM_MEMORY") == "0":
        return None
    path = team_bundle_path(project_path)
    if not path.exists():
        return None
    try:
        bundle = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(bundle, dict):
        return None
    try:
        # Recompute defensively: a malformed/newer-schema bundle (missing
        # source/target) would make _content_hash raise, which must stay a
        # silent no-op rather than break the session/build path.
        content_hash = bundle.get("content_hash") or _content_hash(bundle)
    except Exception:
        return None
    try:
        if store.get_meta(_META_TEAM_HASH) == content_hash:
            return None  # this exact bundle already inherited
    except Exception:
        return None
    try:
        # If the store already has shared edges, merge incoming bundle
        # through quality-weighted conflict resolution instead of plain
        # MAX-merge. Fresh clones (no shared edges) skip the merge.
        scorer = ContributionQualityScorer()
        merger = QualityWeightedMerger(scorer)

        # Export current shared state as the baseline bundle
        current_shared = export_synapse_bundle(store, namespace=SHARED_NAMESPACE)
        existing_shared_count = current_shared.get("counts", {}).get("synapses", 0)

        if existing_shared_count > 0:
            # Re-import scenario: merge with conflict resolution
            # Convert incoming bundle to scored edges via merger
            incoming_scored = scorer.score_bundle(bundle)
            existing_scored = scorer.score_bundle(current_shared)

            # Build an index of existing edges by (source, target)
            existing_index: dict[tuple[str, str], Any] = {
                (e.source, e.target): e for e in existing_scored
            }

            # Merge: for conflicts, quality-weighted resolution
            merged_edges = []
            conflicts = []
            for edge in incoming_scored:
                key = (edge.source, edge.target)
                if key in existing_index:
                    conflict = merger.resolve_conflict(existing_index[key], edge)
                    conflicts.append(conflict)
                    if not conflict.contest:
                        winner = existing_index[key] if conflict.winner == "a" else edge
                        merged_edges.append(winner)
                    # contest → escalates to E3 as review_required
                    else:
                        merged_edges.append(edge)
                else:
                    merged_edges.append(edge)

            # Run peer review gate on all surviving edges (E3)
            gate = PeerReviewGate(scorer)
            final_rows: list[tuple[str, str, float, int]] = []
            promoted_count = 0
            review_count = 0
            rejected_count = 0
            for edge in merged_edges:
                decision = gate.decide(edge)
                if decision.action == "auto_promote":
                    final_rows.append(
                        (edge.source, edge.target, edge.score, edge.activation_count)
                    )
                    promoted_count += 1
                elif decision.action == "review_required":
                    _add_to_pending_review(store, decision)
                    review_count += 1
                else:
                    rejected_count += 1

            written = (
                store.import_edges(final_rows, namespace=SHARED_NAMESPACE)
                if final_rows
                else 0
            )

            decayed_count = sum(
                1
                for c in conflicts
                if c.resolved and c.winner == "b"
            )

            result = {
                "namespace": SHARED_NAMESPACE,
                "synapses": written,
                "promoted": promoted_count,
                "review_required": review_count,
                "rejected": rejected_count,
                "contest": sum(1 for c in conflicts if c.contest),
                "decayed": decayed_count,
                "transitions": 0,
            }
        else:
            # Fresh clone — apply peer review gate before importing
            incoming_scored = scorer.score_bundle(bundle)
            gate = PeerReviewGate(scorer)
            final_rows = []
            review_count = 0
            rejected_count = 0
            for edge in incoming_scored:
                decision = gate.decide(edge)
                if decision.action == "auto_promote":
                    final_rows.append(
                        (edge.source, edge.target, edge.score, edge.activation_count)
                    )
                elif decision.action == "review_required":
                    _add_to_pending_review(store, decision)
                    review_count += 1
                else:
                    rejected_count += 1

            written = (
                store.import_edges(final_rows, namespace=SHARED_NAMESPACE)
                if final_rows
                else 0
            )
            result = {
                "namespace": SHARED_NAMESPACE,
                "synapses": written,
                "promoted": written,
                "review_required": review_count,
                "rejected": rejected_count,
                "contest": 0,
                "decayed": 0,
                "transitions": 0,
            }
    except Exception:
        return None
    # Record the idempotency hash in its own try: a meta-write failure must not
    # discard a successful import (that would lose the summary and re-import the
    # same bundle on every session/build).
    try:
        store.set_meta(_META_TEAM_HASH, content_hash)
    except Exception:
        pass
    result["content_hash"] = content_hash
    return result


__all__ = [
    "TEAM_BUNDLE_FILENAME",
    "team_bundle_path",
    "build_team_bundle",
    "publish_team_memory",
    "maybe_import_team_memory",
    "SYNAPSE_BUNDLE_KIND_TRANSITION",
]
