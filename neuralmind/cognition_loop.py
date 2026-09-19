"""cognition_loop.py — Background knowledge consolidation for NeuralMind.

The cognition loop runs periodically (default every hour) to keep the
synapse layer fresh and consolidate knowledge from recent queries. It
performs four operations:

1. **Reinforce co-access edges** — files that appeared together in recent
   queries get their traversal edges reinforced (Hebbian learning).
2. **Decay unused edges** — edges that haven't been activated recently
   decay faster, pruning stale associations.
3. **Consolidate knowledge** — frequently co-activated node clusters
   are promoted to "durable" status (LTP), making them harder to prune.
4. **Prune stale data** — old session summaries, expired read cache entries,
   and dormant synapses are cleaned up.

The loop is designed to run as a background process (via systemd timer or
cron) or be triggered manually. It is safe to run concurrently with
NeuralMind queries — all operations use SQLite transactions.

Design:
- Stdlib only.
- Idempotent — safe to run multiple times.
- Configurable intervals and thresholds.
- Logs all operations for observability.
"""

from __future__ import annotations

import json
import logging
import os
import sqlite3
import time
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)

# Defaults
DEFAULT_COGNITION_INTERVAL_SECS = 3600  # 1 hour
DEFAULT_MAX_STEPS = 9
DEFAULT_SYNTHESIS_MIN_CLUSTER = 3
DEFAULT_CONSOLIDATE_COOLDOWN_SECS = 120
DEFAULT_DECAY_RATE = 0.6  # per day
DEFAULT_PRUNE_DAYS = 30


def _env_int(name: str, default: int) -> int:
    """Read an int from the environment, falling back on unset/malformed."""
    try:
        return int(os.environ[name])
    except (KeyError, ValueError):
        return default


def _env_float(name: str, default: float) -> float:
    """Read a float from the environment, falling back on unset/malformed."""
    try:
        return float(os.environ[name])
    except (KeyError, ValueError):
        return default


def _env_bool(name: str, default: bool) -> bool:
    """Read a bool from the environment, falling back on unset/malformed."""
    val = os.environ.get(name, "").strip().lower()
    if val in ("1", "true", "yes", "on"):
        return True
    if val in ("0", "false", "no", "off"):
        return False
    return default


@dataclass
class CognitionConfig:
    """Configuration for the cognition loop."""

    enabled: bool = _env_bool("NEURALMIND_COGNITION_LOOP", True)
    interval_secs: int = _env_int(
        "NEURALMIND_COGNITION_INTERVAL_SECS", DEFAULT_COGNITION_INTERVAL_SECS
    )
    max_steps: int = _env_int("NEURALMIND_COGNITION_MAX_STEPS", DEFAULT_MAX_STEPS)
    synthesis_min_cluster: int = _env_int(
        "NEURALMIND_SYNTHESIS_MIN_CLUSTER", DEFAULT_SYNTHESIS_MIN_CLUSTER
    )
    consolidate_cooldown_secs: int = _env_int(
        "NEURALMIND_CONSOLIDATE_COOLDOWN_SECS", DEFAULT_CONSOLIDATE_COOLDOWN_SECS
    )
    decay_rate: float = _env_float("NEURALMIND_DECAY_RATE", DEFAULT_DECAY_RATE)
    prune_days: int = _env_int("NEURALMIND_PRUNE_DAYS", DEFAULT_PRUNE_DAYS)


@dataclass
class CognitionReport:
    """Report of a cognition loop run."""

    timestamp: float
    steps_taken: int
    edges_reinforced: int
    edges_decayed: int
    edges_pruned: int
    clusters_consolidated: int
    summaries_pruned: int
    read_cache_cleared: int
    duration_secs: float

    def to_dict(self) -> dict:
        return {
            "timestamp": self.timestamp,
            "steps_taken": self.steps_taken,
            "edges_reinforced": self.edges_reinforced,
            "edges_decayed": self.edges_decayed,
            "edges_pruned": self.edges_pruned,
            "clusters_consolidated": self.clusters_consolidated,
            "summaries_pruned": self.summaries_pruned,
            "read_cache_cleared": self.read_cache_cleared,
            "duration_secs": self.duration_secs,
        }


class CognitionLoop:
    """Background knowledge consolidation loop.

    Usage:
        loop = CognitionLoop(project_path)
        report = loop.run()
        print(report.to_dict())
    """

    def __init__(
        self,
        project_path: str | Path,
        config: CognitionConfig | None = None,
    ):
        self.project_path = Path(project_path)
        self.config = config or CognitionConfig()
        self.synapses_db = self.project_path / ".neuralmind" / "synapses.db"
        self.summaries_dir = self.project_path / ".neuralmind" / "summaries"
        self.read_cache_dir = self.project_path / ".neuralmind" / "read_cache"

    def run(self) -> CognitionReport:
        """Run one iteration of the cognition loop.

        Returns a report of what was done.
        """
        start = time.time()
        report = CognitionReport(
            timestamp=start,
            steps_taken=0,
            edges_reinforced=0,
            edges_decayed=0,
            edges_pruned=0,
            clusters_consolidated=0,
            summaries_pruned=0,
            read_cache_cleared=0,
            duration_secs=0.0,
        )

        if not self.config.enabled:
            logger.info("[cognition_loop] disabled, skipping")
            return report

        if not self.synapses_db.exists():
            logger.info("[cognition_loop] no synapses db, skipping")
            return report

        logger.info("[cognition_loop] starting (max_steps=%d)", self.config.max_steps)

        for step in range(self.config.max_steps):
            report.steps_taken = step + 1

            # Step 1: Reinforce co-access edges from recent queries
            report.edges_reinforced += self._reinforce_coaccess()

            # Step 2: Decay unused edges
            report.edges_decayed += self._decay_edges()

            # Step 3: Consolidate knowledge (promote clusters to LTP)
            report.clusters_consolidated += self._consolidate_knowledge()

            # Step 4: Prune stale data
            report.edges_pruned += self._prune_stale_edges()
            report.summaries_pruned += self._prune_old_summaries()
            report.read_cache_cleared += self._clear_read_cache()

            # Check cooldown
            elapsed = time.time() - start
            if elapsed > self.config.consolidate_cooldown_secs:
                logger.info("[cognition_loop] cooldown reached after %d steps", step + 1)
                break

        report.duration_secs = time.time() - start
        logger.info(
            "[cognition_loop] completed in %.1fs: %s", report.duration_secs, report.to_dict()
        )
        return report

    def _reinforce_coaccess(self) -> int:
        """Reinforce co-access edges from recent query results.

        Reads the recent_queries log and reinforces edges between files
        that appeared together in query results.
        """
        try:
            recent_queries_path = self.project_path / ".neuralmind" / "recent_queries.jsonl"
            if not recent_queries_path.exists():
                return 0

            # Read recent queries (last 25)
            lines = recent_queries_path.read_text(encoding="utf-8").strip().split("\n")[-25:]
            if not lines:
                return 0

            # Extract node IDs from query results
            # recent_queries.jsonl stores top_hits as list of {"id": ..., "label": ...}
            node_pairs: list[tuple[str, str]] = []
            for line in lines:
                try:
                    entry = json.loads(line)
                    # Extract file IDs from top_hits
                    hits = entry.get("top_hits", [])
                    file_ids = []
                    for hit in hits:
                        fid = hit.get("id", "")
                        if fid:
                            file_ids.append(fid)
                    if len(file_ids) >= 2:
                        # Add every pair
                        for i in range(len(file_ids)):
                            for j in range(i + 1, len(file_ids)):
                                node_pairs.append((file_ids[i], file_ids[j]))
                except Exception:
                    continue

            if not node_pairs:
                return 0

            # Reinforce pairs in the synapse store
            with sqlite3.connect(str(self.synapses_db)) as conn:
                conn.row_factory = sqlite3.Row
                cur = conn.cursor()
                reinforced = 0
                for node_a, node_b in node_pairs:
                    # Canonical ordering
                    if node_a > node_b:
                        node_a, node_b = node_b, node_a
                    # Check if edge exists
                    cur.execute(
                        "SELECT weight, activation_count FROM synapses WHERE node_a = ? AND node_b = ? AND namespace = 'traversal'",
                        (node_a, node_b),
                    )
                    row = cur.fetchone()
                    if row:
                        # Reinforce existing edge
                        new_weight = min(1.0, row["weight"] + 0.30)
                        cur.execute(
                            "UPDATE synapses SET weight = ?, activation_count = activation_count + 1, last_activated = ? WHERE node_a = ? AND node_b = ? AND namespace = 'traversal'",
                            (new_weight, time.time(), node_a, node_b),
                        )
                    else:
                        # Create new edge
                        cur.execute(
                            "INSERT INTO synapses (node_a, node_b, namespace, weight, activation_count, last_activated, created_at) VALUES (?, ?, 'traversal', 0.30, 1, ?, ?)",
                            (node_a, node_b, time.time(), time.time()),
                        )
                    reinforced += 1
                conn.commit()
                return reinforced

        except Exception as e:
            logger.warning("[cognition_loop] reinforce_coaccess failed: %s", e)
            return 0

    def _decay_edges(self) -> int:
        """Decay unused edges (multiplicative decay).

        Skips LTP-protected edges (activation_count >= LTP_THRESHOLD).
        """
        try:
            with sqlite3.connect(str(self.synapses_db)) as conn:
                conn.row_factory = sqlite3.Row
                cur = conn.cursor()
                # Get all edges (skip LTP-protected)
                cur.execute(
                    "SELECT node_a, node_b, weight, last_activated, namespace, activation_count FROM synapses WHERE activation_count < 5"
                )
                rows = cur.fetchall()
                decayed = 0
                for row in rows:
                    # Skip LTP edges (durable)
                    if row["namespace"] == "traversal":
                        # Traversal edges decay faster
                        rate = self.config.decay_rate * 1.5
                    else:
                        rate = self.config.decay_rate
                    # Calculate decay
                    age_days = (time.time() - row["last_activated"]) / 86400
                    decay_factor = max(0.0, 1.0 - (rate * age_days))
                    new_weight = row["weight"] * decay_factor
                    if new_weight < 0.01:
                        # Prune
                        cur.execute(
                            "DELETE FROM synapses WHERE node_a = ? AND node_b = ? AND namespace = ?",
                            (row["node_a"], row["node_b"], row["namespace"]),
                        )
                        decayed += 1
                    else:
                        cur.execute(
                            "UPDATE synapses SET weight = ? WHERE node_a = ? AND node_b = ? AND namespace = ?",
                            (new_weight, row["node_a"], row["node_b"], row["namespace"]),
                        )
                        decayed += 1
                conn.commit()
                return decayed
        except Exception as e:
            logger.warning("[cognition_loop] decay_edges failed: %s", e)
            return 0

    def _consolidate_knowledge(self) -> int:
        """Consolidate knowledge by promoting frequently co-activated clusters.

        Finds clusters of nodes that are frequently co-activated and
        promotes them to LTP (long-term potentiation) status.
        """
        try:
            with sqlite3.connect(str(self.synapses_db)) as conn:
                conn.row_factory = sqlite3.Row
                cur = conn.cursor()
                # Find clusters: nodes with high mutual activation
                cur.execute(
                    """
                    SELECT node_a, node_b, weight, activation_count
                    FROM synapses
                    WHERE namespace = 'traversal'
                    AND activation_count >= ?
                    ORDER BY activation_count DESC
                    LIMIT 50
                    """,
                    (self.config.synthesis_min_cluster,),
                )
                rows = cur.fetchall()
                if not rows:
                    return 0

                # Group by connected components (simple union-find)
                parent: dict[str, str] = {}

                def find(x: str) -> str:
                    if x not in parent:
                        parent[x] = x
                    while parent[x] != x:
                        parent[x] = parent[parent[x]]
                        x = parent[x]
                    return x

                def union(x: str, y: str) -> None:
                    px, py = find(x), find(y)
                    if px != py:
                        parent[px] = py

                for row in rows:
                    union(row["node_a"], row["node_b"])

                # Count cluster sizes
                clusters: dict[str, list[str]] = defaultdict(list)
                for node in parent:
                    clusters[find(node)].append(node)

                # Promote clusters with >= synthesis_min_cluster nodes
                promoted = 0
                for _root, members in clusters.items():
                    if len(members) >= self.config.synthesis_min_cluster:
                        # Promote all edges in this cluster to LTP
                        for i in range(len(members)):
                            for j in range(i + 1, len(members)):
                                a, b = members[i], members[j]
                                if a > b:
                                    a, b = b, a
                                cur.execute(
                                    "UPDATE synapses SET activation_count = MAX(activation_count, 5) WHERE node_a = ? AND node_b = ? AND namespace = 'traversal'",
                                    (a, b),
                                )
                                promoted += 1

                conn.commit()
                return promoted

        except Exception as e:
            logger.warning("[cognition_loop] consolidate_knowledge failed: %s", e)
            return 0

    def _prune_stale_edges(self) -> int:
        """Remove edges that haven't been activated in prune_days."""
        try:
            cutoff = time.time() - (self.config.prune_days * 86400)
            with sqlite3.connect(str(self.synapses_db)) as conn:
                cur = conn.cursor()
                cur.execute(
                    "DELETE FROM synapses WHERE last_activated < ? AND activation_count < 5",
                    (cutoff,),
                )
                pruned = cur.rowcount
                conn.commit()
                return pruned
        except Exception as e:
            logger.warning("[cognition_loop] prune_stale_edges failed: %s", e)
            return 0

    def _prune_old_summaries(self) -> int:
        """Remove session summaries older than prune_days."""
        try:
            if not self.summaries_dir.exists():
                return 0
            cutoff = time.time() - (self.config.prune_days * 86400)
            pruned = 0
            for path in self.summaries_dir.glob("*.md"):
                if path.stat().st_mtime < cutoff:
                    path.unlink()
                    pruned += 1
            return pruned
        except Exception as e:
            logger.warning("[cognition_loop] prune_old_summaries failed: %s", e)
            return 0

    def _clear_read_cache(self) -> int:
        """Clear expired read cache entries."""
        try:
            if not self.read_cache_dir.exists():
                return 0
            cleared = 0
            for path in self.read_cache_dir.glob("*.json"):
                try:
                    data = json.loads(path.read_text(encoding="utf-8"))
                    # Check if all entries are stale
                    now = time.time()
                    stale = all((now - entry.get("last_read", 0)) > 3600 for entry in data.values())
                    if stale:
                        path.unlink()
                        cleared += 1
                except Exception:
                    continue
            return cleared
        except Exception as e:
            logger.warning("[cognition_loop] clear_read_cache failed: %s", e)
            return 0


def run_cognition_loop(
    project_path: str | Path, config: CognitionConfig | None = None
) -> CognitionReport:
    """Run the cognition loop for a project.

    This is the main entry point for the cognition loop. It can be called
    from a cron job, systemd timer, or manually.

    Args:
        project_path: Path to the project root.
        config: Optional configuration override.

    Returns:
        CognitionReport with the results.
    """
    loop = CognitionLoop(project_path, config)
    return loop.run()
