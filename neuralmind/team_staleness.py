"""
E4 — Staleness detection for team baseline edges.

Extends A4's sleep consolidation (already detects stale edges by
namespace) with team-specific decay rules: team edges that haven't
been reinforced in N days decay faster than personal edges, because
a team edge no longer being activated signals the team has moved on.

Requires A4 (sleep consolidation with detect_stale_edges).
Local-first. Stdlib-only. Fail-open.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any

# Stale days for team-shared edges — shorter than personal because a
# team edge with no reinforcement signals the team has moved on.
STALE_DAYS_TEAM_SHARED = 30.0
STALE_DAYS_TEAM_BRANCH = 14.0

# Decay rates for stale edges (multiplier applied to weight)
FAST_DECAY_MULTIPLIER = 5.0  # 5x faster decay when stale


@dataclass
class StaleEdge:
    """A team edge flagged as stale."""

    source: str
    target: str
    namespace: str
    score: float = 0.0
    age_days: float = 0.0
    days_since_last: float = 0.0
    is_stale: bool = False
    fast_decay_eligible: bool = False

    def to_dict(self) -> dict:
        return {
            "source": self.source,
            "target": self.target,
            "namespace": self.namespace,
            "score": round(self.score, 4),
            "age_days": round(self.age_days, 1),
            "days_since_last": round(self.days_since_last, 1),
            "is_stale": self.is_stale,
            "fast_decay_eligible": self.fast_decay_eligible,
        }


class TeamStalenessDetector:
    """
    Detects stale team edges in the synapse store and marks them for
    accelerated decay. Team edges decay faster than personal edges
    when no teammate is reinforcing them.

    Requires A4 (DaemonSleep with detect_stale_edges method) for the
    per-namespace query; this class adds the team-baseline policy on
    top of that mechanism.
    """

    def __init__(
        self,
        stale_days_shared: float = STALE_DAYS_TEAM_SHARED,
        stale_days_branch: float = STALE_DAYS_TEAM_BRANCH,
        fast_decay: float = FAST_DECAY_MULTIPLIER,
    ):
        self.stale_days_shared = stale_days_shared
        self.stale_days_branch = stale_days_branch
        self.fast_decay = fast_decay

    def stale_threshold(self, namespace: str) -> float:
        """Get the stale-day threshold for a namespace."""
        if namespace == "shared":
            return self.stale_days_shared
        if namespace.startswith("branch:"):
            return self.stale_days_branch
        return 60.0  # personal/other: longer stale window

    def is_stale(
        self,
        last_activated_ts: float,
        namespace: str,
        now: float | None = None,
    ) -> bool:
        """Check if an edge is stale based on its namespace threshold."""
        if now is None:
            now = time.time()
        age_days = (now - last_activated_ts) / 86400.0
        return age_days >= self.stale_threshold(namespace)

    def detect_stale_in_store(
        self,
        store: Any,
        *,
        namespace: str = "shared",
    ) -> list[StaleEdge]:
        """
        Query a SynapseStore for stale team edges in a namespace.

        Requires store with _connect() andsynapses table schema including
        last_activated and namespace. Fail-open: returns empty on error.
        """
        stale: list[StaleEdge] = []
        cutoff = time.time() - (self.stale_threshold(namespace) * 86400.0)
        try:
            with store._connect() as conn:
                cur = conn.execute(
                    """SELECT node_a, node_b, namespace, weight, last_activated
                       FROM synapses
                       WHERE namespace = ?
                         AND last_activated < ?
                       ORDER BY weight ASC""",
                    (namespace, cutoff),
                )
                for row in cur.fetchall():
                    node_a, node_b, ns, weight, last_act = row
                    days_since_last = (time.time() - last_act) / 86400.0
                    age_days = days_since_last  # approximate age as staleness
                    stale.append(
                        StaleEdge(
                            source=node_a,
                            target=node_b,
                            namespace=ns,
                            score=weight,
                            age_days=age_days,
                            days_since_last=days_since_last,
                            is_stale=True,
                            fast_decay_eligible=True,
                        )
                    )
        except Exception:
            pass  # fail-open
        return stale

    def mark_fast_decay(
        self,
        store: Any,
        stale_edges: list[StaleEdge],
    ) -> int:
        """
        Apply accelerated decay to a list of stale edges.

        Decay is time-proportional: weight × 2^(−fast_decay × days_past_threshold / half_life).
        After 1 day past stale: 2^(−5/30) ≈ 0.891
        After 30 days past stale: 2^(−5) = 1/32 — matches intent

        Returns the number of edges updated. Fail-open: partial
        failures return the count of successful updates.
        """
        if not stale_edges:
            return 0
        updated = 0
        try:
            with store._connect() as conn:
                conn.execute("BEGIN")
                for edge in stale_edges:
                    if not edge.fast_decay_eligible:
                        continue
                    # Time-proportional decay: scales by days past threshold
                    days_past = max(
                        0.0, edge.days_since_last - self.stale_threshold(edge.namespace)
                    )
                    half_life_days = self.stale_threshold(edge.namespace)
                    decay_exponent = self.fast_decay * days_past / max(1.0, half_life_days)
                    decay_factor = 2.0 ** (-decay_exponent)
                    conn.execute(
                        """UPDATE synapses SET weight = weight * ?
                           WHERE node_a = ? AND node_b = ? AND namespace = ?""",
                        (decay_factor, edge.source, edge.target, edge.namespace),
                    )
                    updated += 1
                conn.execute("COMMIT")
        except Exception:
            pass  # fail-open
        return updated

    def run_staleness_pass(
        self,
        store: Any,
        *,
        namespace: str = "shared",
    ) -> tuple[int, list[StaleEdge]]:
        """
        Full staleness pass: detect stale edges in a namespace and
        mark them for fast decay. Returns (count_updated, stale_edges).
        """
        stale = self.detect_stale_in_store(store, namespace=namespace)
        updated = self.mark_fast_decay(store, stale)
        return updated, stale
