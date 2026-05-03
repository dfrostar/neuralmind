"""
synapses.py — Brain-like associative memory layer for NeuralMind.

A SynapseStore tracks weighted edges between code nodes and learns from
co-activation. It runs as a separate "brain" alongside the LLM: the LLM
fires queries and tool calls, NeuralMind reinforces or decays the
synapses between the nodes those events activated, and future retrievals
spread activation across the resulting graph instead of relying on a
flat top-k vector search.

Design:
- Edges are undirected and stored under canonical ordering (node_a < node_b).
- Reinforcement is Hebbian: nodes that fire together wire together.
- Decay is multiplicative; weights below a prune threshold are deleted.
- Long-term potentiation: edges whose lifetime activation count crosses
  LTP_THRESHOLD have a weight floor and decay slower.
- Hub normalization: nodes with degree above HUB_DEGREE divide outgoing
  contributions by their degree during activation spread, so a single
  utility node can't dominate retrieval.
"""

from __future__ import annotations

import math
import sqlite3
import time
from collections.abc import Iterable
from contextlib import contextmanager
from pathlib import Path

LEARNING_RATE = 0.15
WEIGHT_CAP = 1.0
PRUNE_THRESHOLD = 0.01
DECAY_RATE = 0.02
LTP_THRESHOLD = 5
LTP_FLOOR = 0.20
LTP_DECAY_RATE = 0.005
HUB_DEGREE = 50
SPREAD_DECAY = 0.6
DEFAULT_SPREAD_DEPTH = 2
DEFAULT_SPREAD_TOP_K = 12

SCHEMA = """
CREATE TABLE IF NOT EXISTS synapses (
    node_a TEXT NOT NULL,
    node_b TEXT NOT NULL,
    weight REAL NOT NULL DEFAULT 0.0,
    activation_count INTEGER NOT NULL DEFAULT 0,
    last_activated REAL NOT NULL,
    created_at REAL NOT NULL,
    PRIMARY KEY (node_a, node_b),
    CHECK (node_a < node_b)
);
CREATE INDEX IF NOT EXISTS idx_syn_a ON synapses(node_a);
CREATE INDEX IF NOT EXISTS idx_syn_b ON synapses(node_b);
CREATE INDEX IF NOT EXISTS idx_syn_weight ON synapses(weight);

CREATE TABLE IF NOT EXISTS node_activations (
    node_id TEXT PRIMARY KEY,
    activation_count INTEGER NOT NULL DEFAULT 0,
    last_activated REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS meta (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
"""


def _canonical(a: str, b: str) -> tuple[str, str] | None:
    if a == b:
        return None
    return (a, b) if a < b else (b, a)


class SynapseStore:
    """SQLite-backed associative memory over node ids.

    The store is safe to construct lazily and to share across hooks; each
    call opens a short-lived connection so we don't pin a handle to the
    main thread (the file watcher and MCP server may both write).
    """

    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    @contextmanager
    def _connect(self):
        conn = sqlite3.connect(self.db_path, timeout=5.0, isolation_level=None)
        try:
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA synchronous=NORMAL")
            yield conn
        finally:
            conn.close()

    def _init_schema(self) -> None:
        with self._connect() as conn:
            conn.executescript(SCHEMA)

    def reinforce(
        self,
        node_ids: Iterable[str],
        strength: float = 1.0,
        now: float | None = None,
    ) -> int:
        """Hebbian update: bump weights on every pairwise edge in node_ids.

        Returns the number of pairs touched. Self-pairs and duplicates are
        ignored. Each node's activation counter is also incremented.
        """
        ids = [n for n in dict.fromkeys(node_ids) if n]
        if len(ids) < 2 and not ids:
            return 0
        ts = now if now is not None else time.time()
        delta = LEARNING_RATE * max(0.0, min(strength, 2.0))

        pairs: list[tuple[str, str]] = []
        for i, a in enumerate(ids):
            for b in ids[i + 1 :]:
                pair = _canonical(a, b)
                if pair is not None:
                    pairs.append(pair)

        with self._connect() as conn:
            conn.execute("BEGIN")
            try:
                for node_id in ids:
                    conn.execute(
                        """
                        INSERT INTO node_activations(node_id, activation_count, last_activated)
                        VALUES (?, 1, ?)
                        ON CONFLICT(node_id) DO UPDATE SET
                            activation_count = activation_count + 1,
                            last_activated = excluded.last_activated
                        """,
                        (node_id, ts),
                    )
                for a, b in pairs:
                    conn.execute(
                        """
                        INSERT INTO synapses(
                            node_a, node_b, weight, activation_count,
                            last_activated, created_at
                        ) VALUES (?, ?, ?, 1, ?, ?)
                        ON CONFLICT(node_a, node_b) DO UPDATE SET
                            weight = MIN(?, synapses.weight + ?),
                            activation_count = synapses.activation_count + 1,
                            last_activated = excluded.last_activated
                        """,
                        (a, b, min(WEIGHT_CAP, delta), ts, ts, WEIGHT_CAP, delta),
                    )
                conn.execute("COMMIT")
            except Exception:
                conn.execute("ROLLBACK")
                raise

        return len(pairs)

    def decay(self, now: float | None = None) -> dict:
        """Multiplicatively shrink all weights.

        LTP edges (activation_count >= LTP_THRESHOLD) decay at LTP_DECAY_RATE
        and are floored at LTP_FLOOR. Non-LTP edges decay at DECAY_RATE and
        are pruned below PRUNE_THRESHOLD. Returns counts of decayed and pruned.
        """
        ts = now if now is not None else time.time()
        with self._connect() as conn:
            conn.execute("BEGIN")
            try:
                conn.execute(
                    """
                    UPDATE synapses
                    SET weight = MAX(?, weight * (1.0 - ?))
                    WHERE activation_count >= ?
                    """,
                    (LTP_FLOOR, LTP_DECAY_RATE, LTP_THRESHOLD),
                )
                conn.execute(
                    """
                    UPDATE synapses
                    SET weight = weight * (1.0 - ?)
                    WHERE activation_count < ?
                    """,
                    (DECAY_RATE, LTP_THRESHOLD),
                )
                cur = conn.execute(
                    "DELETE FROM synapses WHERE weight < ? AND activation_count < ?",
                    (PRUNE_THRESHOLD, LTP_THRESHOLD),
                )
                pruned = cur.rowcount
                conn.execute(
                    "INSERT OR REPLACE INTO meta(key, value) VALUES ('last_decay', ?)",
                    (str(ts),),
                )
                conn.execute("COMMIT")
            except Exception:
                conn.execute("ROLLBACK")
                raise
            cur = conn.execute("SELECT COUNT(*) FROM synapses")
            remaining = cur.fetchone()[0]
        return {"pruned": pruned, "remaining": remaining}

    def neighbors(self, node_id: str, k: int = 5) -> list[tuple[str, float]]:
        """Return the strongest neighbors of a single node."""
        with self._connect() as conn:
            cur = conn.execute(
                """
                SELECT CASE WHEN node_a = ? THEN node_b ELSE node_a END AS other,
                       weight
                FROM synapses
                WHERE node_a = ? OR node_b = ?
                ORDER BY weight DESC
                LIMIT ?
                """,
                (node_id, node_id, node_id, k),
            )
            return [(row[0], float(row[1])) for row in cur.fetchall()]

    def _node_degree(self, conn: sqlite3.Connection, node_id: str) -> int:
        cur = conn.execute(
            "SELECT COUNT(*) FROM synapses WHERE node_a = ? OR node_b = ?",
            (node_id, node_id),
        )
        return int(cur.fetchone()[0])

    def spread(
        self,
        seeds: Iterable[tuple[str, float]] | Iterable[str],
        depth: int = DEFAULT_SPREAD_DEPTH,
        top_k: int = DEFAULT_SPREAD_TOP_K,
    ) -> list[tuple[str, float]]:
        """Spreading activation from a set of seed nodes.

        ``seeds`` may be ``[(node_id, energy), ...]`` or just ``[node_id, ...]``
        (each defaulting to energy 1.0). Activation propagates outward along
        weighted edges, decaying by SPREAD_DECAY each hop, with hub
        normalization to prevent runaway central nodes.

        Returns the top_k nodes (excluding seeds) ranked by accumulated
        activation. Empty list if the graph has no relevant edges yet.
        """
        seed_list: list[tuple[str, float]] = []
        for s in seeds:
            if isinstance(s, tuple):
                node_id, energy = s
                seed_list.append((node_id, float(energy)))
            else:
                seed_list.append((str(s), 1.0))
        if not seed_list:
            return []

        activation: dict[str, float] = {}
        for node_id, energy in seed_list:
            activation[node_id] = activation.get(node_id, 0.0) + energy

        seed_ids = {nid for nid, _ in seed_list}
        frontier: dict[str, float] = dict(activation)

        with self._connect() as conn:
            for hop in range(depth):
                if not frontier:
                    break
                next_frontier: dict[str, float] = {}
                for node_id, energy in frontier.items():
                    if energy <= 0.0:
                        continue
                    degree = self._node_degree(conn, node_id)
                    if degree == 0:
                        continue
                    hub_factor = (
                        math.sqrt(HUB_DEGREE / degree) if degree > HUB_DEGREE else 1.0
                    )
                    cur = conn.execute(
                        """
                        SELECT CASE WHEN node_a = ? THEN node_b ELSE node_a END AS other,
                               weight
                        FROM synapses
                        WHERE node_a = ? OR node_b = ?
                        """,
                        (node_id, node_id, node_id),
                    )
                    for other, weight in cur.fetchall():
                        propagated = energy * float(weight) * SPREAD_DECAY * hub_factor
                        if propagated <= 0.0:
                            continue
                        activation[other] = activation.get(other, 0.0) + propagated
                        next_frontier[other] = next_frontier.get(other, 0.0) + propagated
                frontier = next_frontier

        for sid in seed_ids:
            activation.pop(sid, None)

        ranked = sorted(activation.items(), key=lambda x: x[1], reverse=True)
        return ranked[:top_k]

    def normalize_hubs(self, max_degree: int = HUB_DEGREE) -> int:
        """Trim weights on nodes that have grown into runaway hubs.

        For every node with degree > max_degree, scale its incident edges
        by sqrt(max_degree / degree). Returns the number of nodes adjusted.
        """
        with self._connect() as conn:
            cur = conn.execute(
                """
                SELECT node_id, COUNT(*) AS degree FROM (
                    SELECT node_a AS node_id FROM synapses
                    UNION ALL
                    SELECT node_b AS node_id FROM synapses
                )
                GROUP BY node_id
                HAVING degree > ?
                """,
                (max_degree,),
            )
            hubs = cur.fetchall()
            if not hubs:
                return 0
            conn.execute("BEGIN")
            try:
                for node_id, degree in hubs:
                    factor = math.sqrt(max_degree / degree)
                    conn.execute(
                        """
                        UPDATE synapses
                        SET weight = weight * ?
                        WHERE node_a = ? OR node_b = ?
                        """,
                        (factor, node_id, node_id),
                    )
                conn.execute("COMMIT")
            except Exception:
                conn.execute("ROLLBACK")
                raise
        return len(hubs)

    def stats(self) -> dict:
        with self._connect() as conn:
            edges = conn.execute("SELECT COUNT(*) FROM synapses").fetchone()[0]
            ltp_edges = conn.execute(
                "SELECT COUNT(*) FROM synapses WHERE activation_count >= ?",
                (LTP_THRESHOLD,),
            ).fetchone()[0]
            total_weight = conn.execute(
                "SELECT COALESCE(SUM(weight), 0.0) FROM synapses"
            ).fetchone()[0]
            nodes = conn.execute(
                "SELECT COUNT(*) FROM node_activations"
            ).fetchone()[0]
            top_hubs = conn.execute(
                """
                SELECT node_id, COUNT(*) AS degree FROM (
                    SELECT node_a AS node_id FROM synapses
                    UNION ALL
                    SELECT node_b AS node_id FROM synapses
                )
                GROUP BY node_id
                ORDER BY degree DESC
                LIMIT 5
                """
            ).fetchall()
        return {
            "edges": int(edges),
            "ltp_edges": int(ltp_edges),
            "total_weight": float(total_weight),
            "nodes": int(nodes),
            "top_hubs": [(nid, int(deg)) for nid, deg in top_hubs],
            "db_path": str(self.db_path),
        }

    def reset(self) -> None:
        """Drop all synapses and activations. Useful for tests and full retrain."""
        with self._connect() as conn:
            conn.execute("DELETE FROM synapses")
            conn.execute("DELETE FROM node_activations")
            conn.execute("DELETE FROM meta")


def default_db_path(project_path: str | Path) -> Path:
    return Path(project_path) / ".neuralmind" / "synapses.db"
