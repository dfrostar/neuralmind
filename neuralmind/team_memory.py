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
- **`retract_team_edge`** — stop sharing one association: delete it from
  ``shared`` and list it under the bundle's ``retracted`` key. Retractions
  travel with the bundle: importing it deletes the pair from each teammate's
  ``shared`` memory, and publishing never re-adds a retracted pair.

Governance (``neuralmind.tier2.governance``) applies once an operator has set
it up (a tier2 config file exists): ``publish`` honours the publishing scope
and weight threshold, and publishes, imports and removals are written to the
hash-chained audit log. Without that config nothing here is gated or audited.

Imports stay MAX-merge (a bundle can only *raise* the weight of pairs it
asserts) and the ``shared`` namespace decays, so a stale/over-eager bundle can't
permanently distort recall — and it only ever writes ``shared`` (never the
developer's ``personal`` or branch memory).
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import tempfile
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
from .team_staleness import TeamStalenessDetector

logger = logging.getLogger(__name__)

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

# The namespaces a bundle is built from when no governance policy narrows them.
_DEFAULT_SOURCE_NAMESPACES = (DEFAULT_NAMESPACE, SHARED_NAMESPACE)

# publish_team_memory()'s default: read the policy from the tier2 config.
_POLICY_FROM_CONFIG = object()


class PublishBlockedError(PermissionError):
    """Raised when governance forbids ``memory publish`` (scope ``personal``,
    or a governance config that can't be read)."""


def _pair(source: Any, target: Any) -> tuple[str, str] | None:
    """Order-independent key for an association (None for a malformed one)."""
    if not source or not target or source == target:
        return None
    a, b = str(source), str(target)
    return (a, b) if a < b else (b, a)


def _retracted_pairs(bundle: dict[str, Any] | None) -> set[tuple[str, str]]:
    """The associations a bundle retracts."""
    pairs: set[tuple[str, str]] = set()
    for entry in (bundle or {}).get("retracted", []) or []:
        if isinstance(entry, dict):
            pair = _pair(entry.get("source"), entry.get("target"))
            if pair is not None:
                pairs.add(pair)
    return pairs


def _retracted_entries(bundle: dict[str, Any] | None) -> list[dict[str, Any]]:
    """A bundle's retraction list, de-duplicated and in a stable order."""
    seen: dict[tuple[str, str], dict[str, Any]] = {}
    for entry in (bundle or {}).get("retracted", []) or []:
        if not isinstance(entry, dict):
            continue
        pair = _pair(entry.get("source"), entry.get("target"))
        if pair is not None and pair not in seen:
            seen[pair] = {
                "source": pair[0],
                "target": pair[1],
                "retracted_at": str(entry.get("retracted_at", "")),
            }
    return [seen[p] for p in sorted(seen)]


def _read_bundle(path: Path) -> dict[str, Any] | None:
    """The bundle at ``path``, or None when it is missing or unreadable."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return data if isinstance(data, dict) else None


def _write_bundle(path: Path, bundle: dict[str, Any]) -> None:
    """Replace the bundle atomically: a failed write leaves the old file whole."""
    try:
        mode = path.stat().st_mode & 0o777  # keep an existing file's permissions
    except OSError:
        mode = 0o644  # mkstemp's 0600 would be wrong for a committed file
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix=f".{path.name}.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(json.dumps(bundle, indent=2) + "\n")
        os.chmod(tmp, mode)
        os.replace(tmp, path)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise


def _record_team_event(
    action: str, project_path: str | Path, details: dict[str, Any]
) -> bool | None:
    """Audit a team-memory event when governance is configured.

    Returns ``record_team_event``'s result (None = governance not configured).
    Never raises: the tier2 modules are optional at runtime.
    """
    try:
        from .tier2.governance import record_team_event

        return record_team_event(
            action,
            str(Path(project_path).resolve()),
            details,
            project_path=project_path,
        )
    except Exception:
        logger.debug("[team_memory] %s audit skipped", action, exc_info=True)
        return None


def _governance_policy() -> Any:
    """The publish policy from the tier2 config, or None if there isn't one.

    Fails closed: a governance config that exists but can't be read raises
    PublishBlockedError rather than publishing ungoverned memory.
    """
    try:
        from .tier2.governance import load_publish_policy
    except ImportError:
        return None
    try:
        return load_publish_policy()
    except Exception as exc:
        raise PublishBlockedError(
            f"Team governance is configured but its settings could not be read ({exc}). "
            "Fix them (`neuralmind team governance status`) before publishing."
        ) from exc


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
    queue.append(
        {
            "source": decision.edge.source,
            "target": decision.edge.target,
            "score": round(decision.edge.score, 4),
            "reason": decision.reason,
            "reviewer_hint": decision.reviewer_hint,
        }
    )
    _save_pending_review(store, queue)


def _drop_from_pending_review(store: Any, pairs: set[tuple[str, str]]) -> int:
    """Remove retracted associations from the review queue; returns how many."""
    if not pairs:
        return 0
    queue = _load_pending_review(store)
    kept = [e for e in queue if _pair(e.get("source"), e.get("target")) not in pairs]
    if len(kept) != len(queue):
        _save_pending_review(store, kept)
    return len(queue) - len(kept)


def team_bundle_path(project_path: str | Path) -> Path:
    """Path to the committed team-memory bundle for ``project_path``."""
    return Path(project_path) / TEAM_BUNDLE_FILENAME


def _content_hash(bundle: dict[str, Any]) -> str:
    """Stable hash of a bundle's *learned content* (ignores timestamps/provenance).

    Two publishes of the same associations hash identically, so re-importing is
    a no-op even if the provenance header differs. Retractions count as content
    (a new retraction must reach teammates); a bundle without any hashes exactly
    as it did before retractions existed."""
    rows: list[tuple] = []
    for e in bundle.get("synapses", []):
        rows.append(("S", e["source"], e["target"], round(float(e.get("weight", 0.0)), 6)))
    for e in bundle.get("transitions", []):
        rows.append(("T", e["source"], e["target"], round(float(e.get("weight", 0.0)), 6)))
    for a, b in sorted(_retracted_pairs(bundle)):
        rows.append(("R", a, b, 0.0))
    rows.sort()
    return hashlib.sha256(json.dumps(rows, separators=(",", ":")).encode("utf-8")).hexdigest()


def _build_bundle(
    store: Any,
    *,
    namespaces: tuple[str, ...] = _DEFAULT_SOURCE_NAMESPACES,
    min_weight: float = 0.0,
    retracted: list[dict[str, Any]] | None = None,
) -> tuple[dict[str, Any], dict[str, int]]:
    """Build a bundle and report what was left out (see build_team_bundle)."""

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

    retracted_list = _retracted_entries({"retracted": retracted or []})
    blocked = {(r["source"], r["target"]) for r in retracted_list}
    syn: dict[tuple[str, str], dict] = {}
    tr: dict[tuple[str, str], dict] = {}
    for ns in namespaces:
        part = export_synapse_bundle(store, ns)
        for e in part.get("synapses", []):
            _merge(syn, e, "activation_count")
        for e in part.get("transitions", []):
            _merge(tr, e, "count")

    left_out = {"below_threshold": 0, "retracted": 0}
    for key in list(syn):
        if _pair(*key) in blocked:
            del syn[key]
            left_out["retracted"] += 1
        elif float(syn[key].get("weight", 0.0)) < min_weight:
            del syn[key]
            left_out["below_threshold"] += 1
    for key in list(tr):
        if _pair(*key) in blocked:
            del tr[key]
            left_out["retracted"] += 1

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
    if retracted_list:
        bundle["retracted"] = retracted_list
    from . import __version__  # lazy: avoids a circular import at package load

    bundle["content_hash"] = _content_hash(bundle)
    bundle["provenance"] = {
        "tool": "neuralmind",
        "tool_version": __version__,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "source_namespaces": list(namespaces),
    }
    return bundle, left_out


def build_team_bundle(
    store: Any,
    *,
    namespaces: tuple[str, ...] = _DEFAULT_SOURCE_NAMESPACES,
    min_weight: float = 0.0,
    retracted: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Build a portable team bundle, by default from ``personal`` + ``shared``.

    Each ``(source, target)`` pair keeps the MAX of *each* field — weight and
    activation_count/count merge independently — across the source namespaces;
    entries are sorted strongest-first and capped so the committed file stays
    small. ``min_weight`` leaves out weaker synapse edges (transitions are on
    a different scale and are not weight-filtered); ``retracted`` pairs are
    left out entirely and carried in the bundle's ``retracted`` list. The
    bundle imports into ``shared`` by default.
    """
    bundle, _ = _build_bundle(
        store, namespaces=namespaces, min_weight=min_weight, retracted=retracted
    )
    return bundle


def publish_team_memory(
    project_path: str | Path, store: Any, policy: Any = _POLICY_FROM_CONFIG
) -> dict[str, Any]:
    """Write the project's learned memory to the committed team-bundle path.

    ``policy`` defaults to the governance policy in the tier2 config (None
    when governance isn't set up — today's behaviour). With one, the scope
    picks the source namespaces and synapse edges below the weight threshold
    are left out. Retractions already in the committed bundle are carried
    forward and never re-published.

    Returns a summary ``{path, counts, content_hash, governance, left_out,
    audited}``. Records the published hash in the store so we don't re-import
    what we just published.

    Raises:
        PublishBlockedError: governance scope is ``personal``, or the governance
            config exists but can't be read.
    """
    if policy is _POLICY_FROM_CONFIG:
        policy = _governance_policy()
    path = team_bundle_path(project_path)
    if policy is not None and policy.blocks_publishing:
        _record_team_event(
            "publish",
            project_path,
            {"blocked": True, "governance": policy.to_dict(), "bundle": str(path)},
        )
        raise PublishBlockedError(
            f"Team governance scope is '{policy.scope}': memory stays on each machine, "
            "so `memory publish` is disabled. An admin can change it with "
            "`neuralmind team governance set-scope shared|both --admin <email>`."
        )

    namespaces = policy.source_namespaces if policy is not None else _DEFAULT_SOURCE_NAMESPACES
    min_weight = policy.weight_threshold if policy is not None else 0.0
    retracted = _retracted_entries(_read_bundle(path))
    bundle, left_out = _build_bundle(
        store, namespaces=tuple(namespaces), min_weight=min_weight, retracted=retracted
    )
    if policy is not None:
        bundle["provenance"]["governance"] = policy.to_dict()
    _write_bundle(path, bundle)
    try:
        store.set_meta(_META_TEAM_HASH, bundle["content_hash"])
    except Exception:
        pass
    audited = _record_team_event(
        "publish",
        project_path,
        {
            "bundle": str(path),
            "content_hash": bundle["content_hash"],
            "counts": bundle["counts"],
            "left_out": left_out,
            "retracted": len(retracted),
            "governance": policy.to_dict() if policy is not None else None,
        },
    )
    return {
        "path": str(path),
        "counts": bundle["counts"],
        "content_hash": bundle["content_hash"],
        "governance": policy.to_dict() if policy is not None else None,
        "left_out": left_out,
        "audited": audited,
    }


def retract_team_edge(
    project_path: str | Path, store: Any, source: str, target: str
) -> dict[str, Any]:
    """Stop sharing the association between ``source`` and ``target``.

    Deletes it (both directions of any transition too) from this machine's
    ``shared`` namespace and from the pending review queue, drops it from the
    committed bundle and lists it under the bundle's ``retracted`` key —
    creating the bundle if none exists yet, so the retraction is recorded
    where every teammate and every later publish will see it. Commit the
    bundle to share the removal.

    Order matters: the bundle is written first, atomically. If that fails,
    nothing else has changed. If the store update fails afterwards, the
    bundle already carries the retraction and this machine's import hash
    hasn't moved, so the next session's import deletes the pair.

    Raises:
        ValueError: ``source``/``target`` don't name two different nodes, or
            the bundle file exists but isn't valid JSON (it is never
            overwritten blindly).
        OSError: the bundle couldn't be written (local state untouched).
    """
    pair = _pair(source, target)
    if pair is None:
        raise ValueError("source and target must name two different nodes")
    path = team_bundle_path(project_path)
    bundle = _read_bundle(path)
    if bundle is None:
        if path.exists():
            raise ValueError(f"{path} is not a valid team bundle; fix it before retracting")
        bundle, _ = _build_bundle(store, namespaces=())

    before = len(bundle.get("synapses", [])) + len(bundle.get("transitions", []))
    for section in ("synapses", "transitions"):
        bundle[section] = [
            e
            for e in bundle.get(section, [])
            if not (isinstance(e, dict) and _pair(e.get("source"), e.get("target")) == pair)
        ]
    after = len(bundle["synapses"]) + len(bundle["transitions"])
    retracted = _retracted_entries(bundle)
    if pair not in {(r["source"], r["target"]) for r in retracted}:
        retracted.append(
            {
                "source": pair[0],
                "target": pair[1],
                "retracted_at": datetime.now(timezone.utc).isoformat(),
            }
        )
        retracted.sort(key=lambda r: (r["source"], r["target"]))
    bundle["retracted"] = retracted
    bundle["counts"] = {
        "synapses": len(bundle["synapses"]),
        "transitions": len(bundle["transitions"]),
    }
    bundle["content_hash"] = _content_hash(bundle)
    _write_bundle(path, bundle)

    removed = store.delete_edge(source, target, SHARED_NAMESPACE)
    _drop_from_pending_review(store, {pair})
    try:
        # This machine now reflects the edited bundle; don't re-import it.
        store.set_meta(_META_TEAM_HASH, bundle["content_hash"])
    except Exception:
        pass
    return {
        "source": source,
        "target": target,
        "removed_from_store": int(removed.get("edges", 0)) + int(removed.get("transitions", 0)),
        "removed_from_bundle": before - after,
        "bundle": str(path),
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
        # Retractions first: the pair leaves `shared` and the review queue, and
        # a stray copy still listed in the bundle is not imported.
        retracted = _retracted_pairs(bundle)
        retracted_removed = 0
        for a, b in sorted(retracted):
            removed = store.delete_edge(a, b, SHARED_NAMESPACE)
            retracted_removed += int(removed.get("edges", 0))
        _drop_from_pending_review(store, retracted)
        if retracted:
            bundle = dict(bundle)
            for section in ("synapses", "transitions"):
                bundle[section] = [
                    e
                    for e in bundle.get(section, [])
                    if _pair(e.get("source"), e.get("target")) not in retracted
                ]

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
                    final_rows.append((edge.source, edge.target, edge.score, edge.activation_count))
                    promoted_count += 1
                elif decision.action == "review_required":
                    _add_to_pending_review(store, decision)
                    review_count += 1
                else:
                    rejected_count += 1

            written = (
                store.import_edges(final_rows, namespace=SHARED_NAMESPACE) if final_rows else 0
            )

            decayed_count = sum(1 for c in conflicts if c.resolved and c.winner == "b")

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
                    final_rows.append((edge.source, edge.target, edge.score, edge.activation_count))
                elif decision.action == "review_required":
                    _add_to_pending_review(store, decision)
                    review_count += 1
                else:
                    rejected_count += 1

            written = (
                store.import_edges(final_rows, namespace=SHARED_NAMESPACE) if final_rows else 0
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
        result["retracted"] = retracted_removed
    except Exception:
        return None
    # Record the idempotency hash in its own try: a meta-write failure must not
    # discard a successful import (that would lose the summary and re-import the
    # same bundle on every session/build).
    try:
        store.set_meta(_META_TEAM_HASH, content_hash)
    except Exception:
        pass

    # E4 — Staleness pass: run after import so new edges aren't immediately
    # flagged as stale. Detects team edges past the stale threshold and applies
    # accelerated decay.
    try:
        staleness_detector = TeamStalenessDetector()
        staled, _ = staleness_detector.run_staleness_pass(store, namespace=SHARED_NAMESPACE)
        result["decayed"] = result.get("decayed", 0) + staled
    except Exception:
        pass  # fail-open: staleness must never break import

    result["content_hash"] = content_hash
    _record_team_event(
        "import",
        project_path,
        {
            "bundle": str(path),
            **{k: v for k, v in result.items() if k != "namespace"},
        },
    )
    return result


__all__ = [
    "TEAM_BUNDLE_FILENAME",
    "PublishBlockedError",
    "team_bundle_path",
    "build_team_bundle",
    "publish_team_memory",
    "retract_team_edge",
    "maybe_import_team_memory",
    "SYNAPSE_BUNDLE_KIND_TRANSITION",
]
