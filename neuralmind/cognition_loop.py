"""cognition_loop.py — On-demand maintenance pass over a project's learned memory.

``neuralmind cognition-loop`` runs one pass, using the same machinery the
Claude Code hooks use rather than a parallel implementation:

1. **Decay** — :meth:`SynapseStore.decay`: time-based half-life decay (30 days
   for personal and branch memory, 60 for shared team memory, 1 for
   ephemeral), long-term-potentiated edges kept at their floor, edges below
   the prune threshold deleted. Each call charges only the time since the
   previous decay, so running it often never decays anything twice.
2. **Read-dedup cleanup** — drops read-dedup rows untouched for a day
   (:meth:`neuralmind.read_dedup.ReadCache.prune`).

The pass is idempotent and safe to run while NeuralMind is in use, so it can
go in cron or a systemd timer. Nothing schedules it: the ``session-start``
hook already decays at every Claude Code session start and ``neuralmind
watch`` decays every 10 minutes, so it is for setups that run neither — an
MCP-only client, say. Hub normalization is deliberately left to the
``pre-compact`` hook: it scales a hub's edges down on every call, so a
frequent schedule would compound it.

Earlier versions (v3.13 to v4.x) ran their own SQL instead, and it destroyed
learned memory: a linear decay applied to every namespace up to nine times
per run deleted most edges idle for about two days; the same 25 recent
queries were replayed into a ``traversal`` namespace that recall never reads,
nine times per run; clusters were promoted to long-term status without the
repeated use that status is supposed to require; and session summaries older
than 30 days were deleted. All of that is gone. Rows the old pass left in the
``traversal`` namespace are inert; ``neuralmind memory reset --namespace
traversal`` removes them.
"""

from __future__ import annotations

import logging
import time
from dataclasses import asdict, dataclass
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class CognitionReport:
    """What one maintenance pass did (``skipped`` says why it did nothing)."""

    timestamp: float
    edges_pruned: int = 0
    edges_remaining: int = 0
    transitions_pruned: int = 0
    transitions_remaining: int = 0
    read_cache_pruned: int = 0
    duration_secs: float = 0.0
    skipped: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


def run_cognition_loop(project_path: str | Path) -> CognitionReport:
    """Run one maintenance pass for a project. Never creates a store."""
    from .learning import learning_disabled
    from .namespaces import resolve_namespace
    from .read_dedup import ReadCache, read_cache_path
    from .synapses import SynapseStore, default_db_path

    start = time.time()
    report = CognitionReport(timestamp=start)
    if learning_disabled():
        # NEURALMIND_NO_LEARN=1 promises nothing writes to learned memory.
        report.skipped = "NEURALMIND_NO_LEARN=1"
        return report
    db = default_db_path(project_path)
    if not db.exists():
        report.skipped = "no learned memory yet"
        return report

    store = SynapseStore(db, namespace=resolve_namespace(project_path))
    decayed = store.decay()
    report.edges_pruned = int(decayed.get("pruned", 0))
    report.edges_remaining = int(decayed.get("remaining", 0))
    report.transitions_pruned = int(decayed.get("pruned_transitions", 0))
    report.transitions_remaining = int(decayed.get("remaining_transitions", 0))

    if read_cache_path(project_path).exists():
        try:
            report.read_cache_pruned = ReadCache(project_path).prune()
        except Exception as exc:  # the cache is disposable; never fail the pass
            logger.warning("[cognition_loop] read-dedup prune failed: %s", exc)

    report.duration_secs = time.time() - start
    logger.info("[cognition_loop] %s", report.to_dict())
    return report
