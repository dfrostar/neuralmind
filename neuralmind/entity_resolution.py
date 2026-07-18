"""
entity_resolution.py — Entity resolution layer (PRD 2 A2).

Resolves synapse node identity by structural-anchor + normalized-label rather
than exact ID match. When merging team memory or importing bundles, this lets
us recognize that the same code entity surfaced under two different ID
schemes is actually one node — so we can merge/decay rather than duplicate.

Cosine-threshold-based auto-merge (>=0.95) with human-review flag (>0.85).
Required for any real team-memory merge semantics (E2 depends on this).

Design:
- Uses the existing normalize_namespace + norm_label seam.
- Cosine-threshold-based merge: >=0.95 auto-merge, >0.85 human-review flag.
- Fail-open: unresolved entities stay separate (never corrupt the graph).
- Pure and stdlib-only at the module level.
"""

from __future__ import annotations

import math
import re
from collections.abc import Iterable
from dataclasses import dataclass


def norm_label(label: str) -> str:
    """Normalize a node label for identity comparison.

    Lowercases, strips common prefixes/suffixes, collapses non-alphanumerics
    to single underscores. The deterministic, scheme-agnostic key that lets
    "app.auth.handle()" and "app/auth/handle" resolve to the same entity.
    """
    s = label.strip().lower()
    s = re.sub(r"[^a-z0-9]+", "_", s)
    return re.sub(r"_+", "_", s).strip("_")


def _tok(text: str) -> set[str]:
    """Lowercase alphanumeric tokens from arbitrary text."""
    return set(re.findall(r"[a-z0-9]+", text.lower()))


def cosine_similarity(set_a: set[str], set_b: set[str]) -> float:
    """Jaccard-like overlap coefficient for token sets.

    Pure-stdlib cosine over token sets: |A ∩ B| / sqrt(|A| * |B|).
    Returns 0.0 when either set is empty.
    """
    if not set_a or not set_b:
        return 0.0
    intersection = set_a & set_b
    denom = math.sqrt(len(set_a) * len(set_b))
    if denom <= 0.0:
        return 0.0
    return len(intersection) / denom


# ---------------------------------------------------------------------------
# Thresholds (PRD 2 A2)
# ---------------------------------------------------------------------------
AUTO_MERGE_THRESHOLD = 0.95
REVIEW_FLAG_THRESHOLD = 0.85


@dataclass
class EntityKey:
    """A normalized entity identity for resolution."""

    raw_label: str
    norm: str
    tokens: set[str]
    structural_anchor: str | None = None

    @classmethod
    def from_label(cls, label: str, anchor: str | None = None) -> EntityKey:
        return cls(
            raw_label=label,
            norm=norm_label(label),
            tokens=_tok(label),
            structural_anchor=anchor,
        )


@dataclass
class ResolutionResult:
    """Outcome of an entity resolution attempt."""

    status: str  # "merge" | "review" | "distinct"
    confidence: float
    target_id: str | None = None
    message: str = ""

    def to_dict(self) -> dict:
        return {
            "status": self.status,
            "confidence": round(self.confidence, 4),
            "target_id": self.target_id,
            "message": self.message,
        }


class EntityResolver:
    """Resolves entity identity across ID schemes using normalized labels.

    Callers register known entities (from the existing graph) and then
    resolve incoming entities (from an imported bundle or another agent's
    namespace) against them. Three outcomes:
    - "merge": high-confidence match (auto-merge).
    - "review": medium-confidence match (flag for human review).
    - "distinct": no match above threshold (keep separate).
    """

    def __init__(
        self,
        *,
        auto_merge_threshold: float = AUTO_MERGE_THRESHOLD,
        review_threshold: float = REVIEW_FLAG_THRESHOLD,
    ):
        self.auto_merge_threshold = auto_merge_threshold
        self.review_threshold = review_threshold
        # (norm_label, structural_anchor) → (entity_id, EntityKey) for registered entities.
        # The anchor disambiguates same-norm labels (e.g., auth.Handle vs auth_handle).
        self._entities: dict[tuple[str, str | None], tuple[str, EntityKey]] = {}

    def register(self, entity_id: str, label: str, anchor: str | None = None) -> None:
        """Register an existing graph entity for resolution."""
        key = EntityKey.from_label(label, anchor=anchor)
        self._entities[(key.norm, anchor)] = (entity_id, key)

    def register_many(self, entities: Iterable[tuple[str, str, str | None]]) -> None:
        """Register many entities at once: (entity_id, label, anchor?)."""
        for entity_id, label, anchor in entities:
            self.register(entity_id, label, anchor=anchor)

    def resolve(self, label: str, anchor: str | None = None) -> ResolutionResult:
        """Resolve an incoming entity against registered entities.

        Returns a ResolutionResult indicating whether to merge, flag for
        review, or treat as distinct. Confidence is the cosine similarity
        of the token sets.
        """
        incoming = EntityKey.from_label(label, anchor=anchor)
        if not incoming.tokens:
            return ResolutionResult(
                status="distinct",
                confidence=0.0,
                message="empty label, cannot resolve",
            )

        # Fast path: exact normalized match.
        if (incoming.norm, anchor) in self._entities:
            target_id, _ = self._entities[(incoming.norm, anchor)]
            return ResolutionResult(
                status="merge",
                confidence=1.0,
                target_id=target_id,
                message=f"exact norm+anchor match: {incoming.norm}@{anchor}",
            )

        # Slow path: cosine similarity against all registered entities.
        best_id: str | None = None
        best_confidence = 0.0
        for (_norm, _reg_anchor), (eid, key) in self._entities.items():
            # Cheap pre-filter: if either token set is empty or label prefixes
            # differ, skip the full cosine.
            if not key.tokens:
                continue
            conf = cosine_similarity(incoming.tokens, key.tokens)
            if conf > best_confidence:
                best_confidence = conf
                best_id = eid

        if best_confidence >= self.auto_merge_threshold:
            return ResolutionResult(
                status="merge",
                confidence=best_confidence,
                target_id=best_id,
                message=f"high-confidence merge ({best_confidence:.3f})",
            )
        if best_confidence >= self.review_threshold:
            return ResolutionResult(
                status="review",
                confidence=best_confidence,
                target_id=best_id,
                message=f"medium-confidence match ({best_confidence:.3f}), review flagged",
            )
        return ResolutionResult(
            status="distinct",
            confidence=best_confidence,
            message=f"no match above threshold ({best_confidence:.3f})",
        )

    def resolve_many(self, labels: Iterable[str]) -> list[ResolutionResult]:
        """Resolve multiple entities. Convenience wrapper."""
        return [self.resolve(label) for label in labels]

    def stats(self) -> dict:
        return {
            "registered_entities": len(self._entities),
            "auto_merge_threshold": self.auto_merge_threshold,
            "review_threshold": self.review_threshold,
        }
