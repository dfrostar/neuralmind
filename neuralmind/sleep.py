"""sleep.py — offline daemon sleep pass for memory consolidation (A4).

Scheduled (weekly, configurable via NEURALMIND_SLEEP_INTERVAL_DAYS):
- Prune redundant edges (below PRUNE_THRESHOLD, no reinforcement in N days)
- Promote LTP edges that survived decay
- Emit consolidated team-baseline bundle
- Detect stale team edges (no reinforcement in N days)

Runs offline, fail-open: any error during a sub-step is logged and
other sub-steps continue; never blocks query/build/search.

See Also:
    - ``neuralmind/contracts.py`` — sleep meta key constants
    - ``neuralmind/learned_decay.py`` — decay integration in sleep
    - ``tests/test_sleep.py`` — test cases

Version:
    0.53.0
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .contracts import (
    META_SLEEP_LAST_RUN,
)

log = logging.getLogger(__name__)


@dataclass
class SleepStats:
    """Result of a sleep pass."""

    pruned: int = 0
    promoted: int = 0
    stale_team_edges: int = 0
    bundle_emitted: bool = False
    ts: float = field(default_factory=time.time)

    def to_dict(self) -> dict:
        return {
            "pruned": self.pruned,
            "promoted": self.promoted,
            "stale_team_edges": self.stale_team_edges,
            "bundle_emitted": self.bundle_emitted,
            "ts": self.ts,
        }


class DaemonSleep:
    """Sleep consolidation pass."""

    def __init__(
        self,
        project_path: str | Path | None = None,
        interval_days: float = 7.0,
        stale_days: float = 60.0,
        prune_threshold: float = 0.01,
    ):
        self.project_path = Path(project_path) if project_path is not None else None
        self.interval_days = interval_days
        self.stale_days = stale_days
        self.prune_threshold = prune_threshold

    # ------------------------------------------------------------------- #
    # Scheduling gate
    # ------------------------------------------------------------------- #

    def should_run(self) -> bool:
        """Check if enough time has passed since last sleep."""
        if self.project_path is None:
            return False
        try:
            store = self._store()
            raw = store.get_meta(META_SLEEP_LAST_RUN)
            if not raw:
                return True
            last = float(raw)
            return (time.time() - last) >= (self.interval_days * 86400)
        except Exception:
            return True

    def mark_run(self) -> None:
        """Stamp last-run timestamp."""
        try:
            store = self._store()
            store.set_meta(META_SLEEP_LAST_RUN, str(time.time()))
        except Exception:
            pass

    # ------------------------------------------------------------------- #
    # Main entry
    # ------------------------------------------------------------------- #

    def run(self) -> SleepStats:
        """Execute the sleep pass (fail-open)."""
        stats = SleepStats()
        if self.project_path is None:
            return stats

        try:
            from .synapses import SynapseStore, default_db_path

            self.store = SynapseStore(default_db_path(self.project_path))
        except Exception as exc:
            log.warning("DaemonSleep: cannot open store: %s", exc)
            return stats

        try:
            stats.pruned = self.prune_redundant_edges()
        except Exception as exc:
            log.warning("DaemonSleep: prune_redundant_edges failed: %s", exc)

        try:
            stats.promoted = self.promote_ltp_edges()
        except Exception as exc:
            log.warning("DaemonSleep: promote_ltp_edges failed: %s", exc)

        try:
            bundle = self.emit_team_bundle()
            stats.bundle_emitted = bundle is not None
        except Exception as exc:
            log.warning("DaemonSleep: emit_team_bundle failed: %s", exc)

        try:
            stale = self._run_staleness_decay()
            stats.stale_team_edges = len(stale)
        except Exception as exc:
            log.warning("DaemonSleep: staleness decay failed: %s", exc)

        self.mark_run()
        return stats

    # ------------------------------------------------------------------- #
    # Sub-steps
    # ------------------------------------------------------------------- #

    def prune_redundant_edges(self) -> int:
        """Prune edges below PRUNE_THRESHOLD with no reinforcement in N days.

        A reinforcement = an activation_count increase since created_at. We
        approximate this by checking last_activated against created_at + N_days.
        Edges that never got reinforced after creation are considered
        redundant (the seeding pass creates many low-weight candidates that
        never see real use).
        """
        cutoff = time.time() - (self.stale_days * 86400)
        with self.store._connect() as conn:
            # Delete edges that are low-weight and haven't been activated
            # since initial creation (no reinforcement).
            cur = conn.execute(
                """DELETE FROM synapses
                   WHERE weight < ?
                     AND activation_count <= 1
                     AND last_activated < ?
                     AND created_at < ?""",
                (self.prune_threshold, cutoff, cutoff),
            )
            return cur.rowcount

    def promote_ltp_edges(self) -> int:
        """Gradually restore LTP edges toward their pre-decay weight.

        LTP edges (activation_count >= LTP_THRESHOLD) are floored at
        LTP_FLOOR during decay, but repeated decay cycles can leave them
        well below their original weight. This pass applies a small
        multiplicative restoration (1.1x) to nudge them back up.

        NOTE: This is gradual restoration, not full restoration. We do
        not track pre-decay weight, so we cannot restore exactly. The
        multiplier is chosen so that edges converge toward WEIGHT_CAP
        over multiple sleep passes without overshooting.
        """
        with self.store._connect() as conn:
            cur = conn.execute(
                """UPDATE synapses SET weight = MIN(1.0, weight * 1.1)
                   WHERE activation_count >= 5
                     AND weight >= 0.20
                     AND weight < 1.0"""
            )
            return cur.rowcount

    def emit_team_bundle(self) -> dict[str, Any] | None:
        """Emit consolidated team-baseline bundle (shared namespace).

        Returns the bundle dict (also persisted to the meta table for
        inspection), or ``None`` if the shared namespace is empty.
        """
        try:
            with self.store._connect() as conn:
                cur = conn.execute(
                    """SELECT node_a, node_b, weight, activation_count
                       FROM synapses WHERE namespace = 'shared'
                       ORDER BY weight DESC
                       LIMIT 500"""
                )
                rows = cur.fetchall()
            if not rows:
                return None
            bundle = {
                "team_baseline": [
                    {
                        "node_a": r[0],
                        "node_b": r[1],
                        "weight": r[2],
                        "activation_count": r[3],
                    }
                    for r in rows
                ],
                "ts": time.time(),
            }
            try:
                self.store.set_meta(
                    "self_improve:team_bundle",
                    json.dumps(bundle, default=str),
                )
            except Exception:
                pass
            return bundle
        except Exception as exc:
            log.debug("emit_team_bundle failed: %s", exc)
            return None

    def detect_stale_edges(self) -> list[str]:
        """Flag edges with no reinforcement in N days (all namespaces)."""
        cutoff = time.time() - (self.stale_days * 86400)
        with self.store._connect() as conn:
            cur = conn.execute(
                """SELECT node_a, node_b, namespace FROM synapses
                   WHERE last_activated < ?
                   ORDER BY weight ASC""",
                (cutoff,),
            )
            return [f"{r[2]}:{r[0]}-{r[1]}" for r in cur.fetchall()]

    def _run_staleness_decay(self) -> list:
        """Apply E4 stale-edge decay via TeamStalenessDetector.

        Runs staleness passes for shared and branch namespaces.
        Returns list of all stale edges detected.
        """
        from .team_staleness import TeamStalenessDetector

        total_stale = []
        detector = TeamStalenessDetector()
        for ns in ("shared", "branch:live"):
            try:
                _, stale = detector.run_staleness_pass(self.store, namespace=ns)
                total_stale.extend(stale)
            except Exception as exc:
                log.debug("staleness pass failed for %s: %s", ns, exc)
        return total_stale

    def _store(self) -> Any:
        if self.project_path is None:
            raise RuntimeError("DaemonSleep: project_path required")
        from .synapses import SynapseStore, default_db_path

        return SynapseStore(default_db_path(self.project_path))
