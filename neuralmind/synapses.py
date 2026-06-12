"""
synapses.py — Brain-like associative memory layer for NeuralMind.

A SynapseStore tracks weighted edges between code nodes and learns from
co-activation. It runs as a separate "brain" alongside the LLM: the LLM
fires queries and tool calls, NeuralMind reinforces or decays the
synapses between the nodes those events activated, and future retrievals
spread activation across the resulting graph instead of relying on a
flat top-k vector search.

Two parallel signals:

- ``synapses`` table — undirected co-activation. "These nodes were
  touched together" with no ordering.
- ``synapse_transitions`` table *(v0.11.0+)* — directional, ordered
  transitions. "After touching A, you touched B." Lets callers ask
  ``next_likely(node)`` for a probability distribution over what
  typically follows. Same Hebbian + decay machinery, separate semantics.

Memory namespaces *(PRD 4)*:

Every synapse, transition, and activation row carries a ``namespace`` so
different kinds of memory don't pollute each other:

- ``personal`` — the default. All pre-namespace memory migrates here, so
  the single-namespace behavior users already have *is* the personal
  namespace.
- ``shared`` — an imported team baseline (PRD 8 bundles land here).
- ``branch:<name>`` — per-git-branch working memory.
- ``ephemeral`` — session-scoped scratch; decays fast and is cleared at
  session boundaries.

Namespaces are plain strings (no enum table) so import/export and new
kinds stay trivial. Writes go to the store's active namespace (the
``namespace`` constructor argument, resolved by the caller — the store
itself is git-agnostic). Reads default to a *merged* view documented at
``MERGED-READ WEIGHTING`` below; passing ``namespaces=[...]`` reads only
those namespaces at their raw weights.

Design:
- Undirected edges are stored under canonical ordering (node_a < node_b).
- Reinforcement is Hebbian: nodes that fire together wire together.
- Decay is multiplicative; weights below a prune threshold are deleted.
- Long-term potentiation: edges whose lifetime activation count crosses
  LTP_THRESHOLD have a weight floor and decay slower.
- Hub normalization: nodes with degree above HUB_DEGREE divide outgoing
  contributions by their degree during activation spread, so a single
  utility node can't dominate retrieval.
- Transitions decay slower than undirected edges (sequential signals are
  rarer and noisier; we want them to accumulate before fading).
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

TRANSITION_LEARNING_RATE = 1.0
TRANSITION_WEIGHT_CAP = 100.0
TRANSITION_DECAY_RATE = 0.01
TRANSITION_PRUNE_THRESHOLD = 0.5
DEFAULT_NEXT_TOP_K = 5

# --------------------------------------------------------------------------- #
# Memory namespaces (PRD 4)
# --------------------------------------------------------------------------- #

SCHEMA_VERSION = 1

DEFAULT_NAMESPACE = "personal"
SHARED_NAMESPACE = "shared"
EPHEMERAL_NAMESPACE = "ephemeral"
BRANCH_NAMESPACE_PREFIX = "branch:"

# MERGED-READ WEIGHTING. When a read method gets ``namespaces=None`` it
# merges the active namespace + ``personal`` + ``shared``, scaling each
# namespace's weights by exactly one of these constants and summing per
# edge:
#
#   merged_weight = W_BRANCH * w_active + W_PERSONAL * w_personal
#                 + W_SHARED * w_shared
#
# - The *active* namespace (whatever the store writes to — a feature
#   branch, ``ephemeral``, or ``personal`` itself on the default branch)
#   always reads at W_BRANCH, so recent branch-local context wins.
# - ``personal``, when it is not the active namespace, reads at
#   W_PERSONAL — useful long-term priors, slightly behind the branch.
# - ``shared`` reads at W_SHARED — imported team baseline, never louder
#   than your own memory.
#
# On the default branch the active namespace *is* personal, so it reads
# at W_BRANCH (1.0) and merged behavior is identical to the
# pre-namespace store. Explicit ``namespaces=[...]`` reads skip these
# multipliers entirely (raw weights), so inspect/export see exact values.
W_BRANCH = 1.0
W_PERSONAL = 0.8
W_SHARED = 0.5

# Per-namespace decay policy. Namespaces not named here (personal,
# branch:*, and any custom name) decay at the default DECAY_RATE /
# TRANSITION_DECAY_RATE above.
#
# - ``shared`` is sticky: a team baseline shouldn't evaporate because one
#   developer stopped touching that area (matches the LTP decay rate).
# - ``ephemeral`` is session scratch: it decays fast, gets no LTP floor,
#   and is cleared outright at session boundaries (SessionStart hook,
#   daemon shutdown) via ``clear_namespace``.
SHARED_DECAY_RATE = 0.005
EPHEMERAL_DECAY_RATE = 0.25
SHARED_TRANSITION_DECAY_RATE = 0.0025
EPHEMERAL_TRANSITION_DECAY_RATE = 0.25

NAMESPACE_DECAY_RATES: dict[str, float] = {
    SHARED_NAMESPACE: SHARED_DECAY_RATE,
    EPHEMERAL_NAMESPACE: EPHEMERAL_DECAY_RATE,
}
NAMESPACE_TRANSITION_DECAY_RATES: dict[str, float] = {
    SHARED_NAMESPACE: SHARED_TRANSITION_DECAY_RATE,
    EPHEMERAL_NAMESPACE: EPHEMERAL_TRANSITION_DECAY_RATE,
}

SCHEMA = f"""
CREATE TABLE IF NOT EXISTS synapses (
    node_a TEXT NOT NULL,
    node_b TEXT NOT NULL,
    namespace TEXT NOT NULL DEFAULT '{DEFAULT_NAMESPACE}',
    weight REAL NOT NULL DEFAULT 0.0,
    activation_count INTEGER NOT NULL DEFAULT 0,
    last_activated REAL NOT NULL,
    created_at REAL NOT NULL,
    PRIMARY KEY (node_a, node_b, namespace),
    CHECK (node_a < node_b)
);
CREATE INDEX IF NOT EXISTS idx_syn_a ON synapses(node_a);
CREATE INDEX IF NOT EXISTS idx_syn_b ON synapses(node_b);
CREATE INDEX IF NOT EXISTS idx_syn_weight ON synapses(weight);
CREATE INDEX IF NOT EXISTS idx_syn_ns ON synapses(namespace, weight);

CREATE TABLE IF NOT EXISTS synapse_transitions (
    from_node TEXT NOT NULL,
    to_node TEXT NOT NULL,
    namespace TEXT NOT NULL DEFAULT '{DEFAULT_NAMESPACE}',
    weight REAL NOT NULL DEFAULT 0.0,
    count INTEGER NOT NULL DEFAULT 0,
    last_activated REAL NOT NULL,
    created_at REAL NOT NULL,
    PRIMARY KEY (from_node, to_node, namespace),
    CHECK (from_node <> to_node)
);
CREATE INDEX IF NOT EXISTS idx_trans_from ON synapse_transitions(from_node);
CREATE INDEX IF NOT EXISTS idx_trans_weight ON synapse_transitions(weight);
CREATE INDEX IF NOT EXISTS idx_trans_ns ON synapse_transitions(namespace, weight);

CREATE TABLE IF NOT EXISTS node_activations (
    node_id TEXT NOT NULL,
    namespace TEXT NOT NULL DEFAULT '{DEFAULT_NAMESPACE}',
    activation_count INTEGER NOT NULL DEFAULT 0,
    last_activated REAL NOT NULL,
    PRIMARY KEY (node_id, namespace)
);

CREATE TABLE IF NOT EXISTS meta (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
"""

# Index names from the v0 (pre-namespace) schema. ALTER TABLE ... RENAME
# keeps indexes attached under their original names, so the migration must
# drop them before the v1 CREATE INDEX statements can reuse those names.
_V0_INDEXES = (
    "idx_syn_a",
    "idx_syn_b",
    "idx_syn_weight",
    "idx_trans_from",
    "idx_trans_weight",
)

_DATA_TABLES = ("synapses", "synapse_transitions", "node_activations")


def _canonical(a: str, b: str) -> tuple[str, str] | None:
    if a == b:
        return None
    return (a, b) if a < b else (b, a)


def normalize_namespace(namespace: str) -> str:
    """Validate and normalize a namespace string.

    Namespaces are plain, single-token strings (``personal``, ``shared``,
    ``ephemeral``, ``branch:<name>``, or any custom name). Raises
    ``ValueError`` on empty or whitespace-containing values so a malformed
    namespace fails loudly at the write site instead of silently forking
    memory.
    """
    if not isinstance(namespace, str):
        raise ValueError(f"namespace must be a string, got {type(namespace).__name__}")
    ns = namespace.strip()
    if not ns:
        raise ValueError("namespace must be a non-empty string")
    if any(ch.isspace() for ch in ns):
        raise ValueError(f"namespace must not contain whitespace: {namespace!r}")
    return ns


def merge_weight_for(namespace: str, active_namespace: str) -> float:
    """The multiplier a namespace's weights get in a merged read.

    See the MERGED-READ WEIGHTING comment above the W_* constants: the
    active namespace reads at W_BRANCH, non-active ``personal`` at
    W_PERSONAL, ``shared`` at W_SHARED. Any other merged-in namespace
    reads at W_PERSONAL.
    """
    if namespace == active_namespace:
        return W_BRANCH
    if namespace == SHARED_NAMESPACE:
        return W_SHARED
    return W_PERSONAL


class SynapseStore:
    """SQLite-backed associative memory over node ids.

    The store is safe to construct lazily and to share across hooks; each
    call opens a short-lived connection so we don't pin a handle to the
    main thread (the file watcher and MCP server may both write).

    ``namespace`` is the *active* namespace: where writes land and which
    namespace reads at full weight in the merged default view. Callers
    resolve it (config / git branch / env — see
    :mod:`neuralmind.namespaces`); the store itself is git-agnostic.
    """

    def __init__(self, db_path: str | Path, namespace: str | None = None):
        self.db_path = Path(db_path)
        self.namespace = normalize_namespace(namespace) if namespace else DEFAULT_NAMESPACE
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

    # ----------------------------------------------------------------- #
    # Schema + migration (PRD 4)
    # ----------------------------------------------------------------- #

    def _init_schema(self) -> None:
        with self._connect() as conn:
            if self._table_exists(conn, "synapses") and not self._has_column(
                conn, "synapses", "namespace"
            ):
                self._migrate_v0_to_v1(conn)
                return
            conn.executescript(SCHEMA)
            self._stamp_schema_version(conn)

    @staticmethod
    def _table_exists(conn: sqlite3.Connection, name: str) -> bool:
        cur = conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (name,))
        return cur.fetchone() is not None

    @staticmethod
    def _has_column(conn: sqlite3.Connection, table: str, column: str) -> bool:
        cur = conn.execute(f"PRAGMA table_info({table})")
        return any(row[1] == column for row in cur.fetchall())

    @staticmethod
    def _stamp_schema_version(conn: sqlite3.Connection) -> None:
        # Only ever raise the recorded version — a db touched by a newer
        # NeuralMind must keep its newer marker.
        cur = conn.execute("SELECT value FROM meta WHERE key='schema_version'")
        row = cur.fetchone()
        try:
            recorded = int(row[0]) if row is not None else 0
        except (TypeError, ValueError):
            recorded = 0
        if recorded < SCHEMA_VERSION:
            conn.execute(
                "INSERT OR REPLACE INTO meta(key, value) VALUES ('schema_version', ?)",
                (str(SCHEMA_VERSION),),
            )

    def _migrate_v0_to_v1(self, conn: sqlite3.Connection) -> None:
        """Rebuild the v0 (pre-namespace) tables into the v1 schema in place.

        SQLite cannot ALTER a primary key, so each data table is renamed,
        recreated with ``namespace`` folded into its PK, copied row-for-row
        into the ``personal`` namespace, and dropped. Everything runs in one
        IMMEDIATE transaction: any failure rolls the whole migration back,
        leaving the v0 database untouched — a migration bug must never
        silently corrupt learned memory.
        """
        conn.execute("BEGIN IMMEDIATE")
        try:
            for table in _DATA_TABLES:
                if self._table_exists(conn, table):
                    conn.execute(f"ALTER TABLE {table} RENAME TO {table}_v0")
            for index in _V0_INDEXES:
                conn.execute(f"DROP INDEX IF EXISTS {index}")
            # CREATE TABLE / CREATE INDEX statements only — executescript()
            # would issue an implicit COMMIT mid-migration, so run each
            # statement through the explicit transaction instead.
            for statement in SCHEMA.split(";"):
                if statement.strip():
                    conn.execute(statement)
            if self._table_exists(conn, "synapses_v0"):
                conn.execute(
                    """
                    INSERT INTO synapses(
                        node_a, node_b, namespace, weight, activation_count,
                        last_activated, created_at
                    )
                    SELECT node_a, node_b, ?, weight, activation_count,
                           last_activated, created_at
                    FROM synapses_v0
                    """,
                    (DEFAULT_NAMESPACE,),
                )
                conn.execute("DROP TABLE synapses_v0")
            if self._table_exists(conn, "synapse_transitions_v0"):
                conn.execute(
                    """
                    INSERT INTO synapse_transitions(
                        from_node, to_node, namespace, weight, count,
                        last_activated, created_at
                    )
                    SELECT from_node, to_node, ?, weight, count,
                           last_activated, created_at
                    FROM synapse_transitions_v0
                    """,
                    (DEFAULT_NAMESPACE,),
                )
                conn.execute("DROP TABLE synapse_transitions_v0")
            if self._table_exists(conn, "node_activations_v0"):
                conn.execute(
                    """
                    INSERT INTO node_activations(
                        node_id, namespace, activation_count, last_activated
                    )
                    SELECT node_id, ?, activation_count, last_activated
                    FROM node_activations_v0
                    """,
                    (DEFAULT_NAMESPACE,),
                )
                conn.execute("DROP TABLE node_activations_v0")
            self._stamp_schema_version(conn)
            conn.execute("COMMIT")
        except Exception:
            conn.execute("ROLLBACK")
            raise

    def get_meta(self, key: str, default: str | None = None) -> str | None:
        """Read a value from the key-value ``meta`` table.

        The ``meta`` table is namespace-free (one row per key for the whole
        store), so values written here are global per project regardless of
        the store's active namespace. Used by the self-improvement engine to
        persist tuner state (``self_improve:*`` keys) across sessions.
        """
        with self._connect() as conn:
            cur = conn.execute("SELECT value FROM meta WHERE key = ?", (key,))
            row = cur.fetchone()
            return row[0] if row is not None else default

    def set_meta(self, key: str, value: object) -> None:
        """Write a value to the key-value ``meta`` table (coerced via ``str``)."""
        with self._connect() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO meta(key, value) VALUES (?, ?)",
                (key, str(value)),
            )

    def schema_version(self) -> int:
        """The schema version recorded in the ``meta`` table (0 = pre-v1)."""
        with self._connect() as conn:
            cur = conn.execute("SELECT value FROM meta WHERE key='schema_version'")
            row = cur.fetchone()
        try:
            return int(row[0]) if row is not None else 0
        except (TypeError, ValueError):
            return 0

    # ----------------------------------------------------------------- #
    # Namespace selection for reads
    # ----------------------------------------------------------------- #

    def _read_namespaces(self, namespaces: list[str] | None) -> list[tuple[str, float]]:
        """Resolve a read's namespace set to ``[(namespace, multiplier), ...]``.

        ``None`` selects the merged default — active + personal + shared,
        each at its documented W_* multiplier. An explicit list reads only
        those namespaces at raw weight (multiplier 1.0).
        """
        if namespaces is None:
            merged = dict.fromkeys((self.namespace, DEFAULT_NAMESPACE, SHARED_NAMESPACE))
            return [(ns, merge_weight_for(ns, self.namespace)) for ns in merged]
        return [(ns, 1.0) for ns in dict.fromkeys(namespaces) if ns]

    # ----------------------------------------------------------------- #
    # Writes
    # ----------------------------------------------------------------- #

    def reinforce(
        self,
        node_ids: Iterable[str],
        strength: float = 1.0,
        now: float | None = None,
        namespace: str | None = None,
    ) -> int:
        """Hebbian update: bump weights on every pairwise edge in node_ids.

        Returns the number of pairs touched. Self-pairs and duplicates are
        ignored. Each node's activation counter is also incremented. Writes
        land in ``namespace`` (default: the store's active namespace).
        """
        ids = [n for n in dict.fromkeys(node_ids) if n]
        # A single node creates no pairs but still bumps its activation
        # counter — lone activations feed the hub/stats signals.
        if not ids:
            return 0
        ns = normalize_namespace(namespace) if namespace else self.namespace
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
                        INSERT INTO node_activations(
                            node_id, namespace, activation_count, last_activated
                        )
                        VALUES (?, ?, 1, ?)
                        ON CONFLICT(node_id, namespace) DO UPDATE SET
                            activation_count = activation_count + 1,
                            last_activated = excluded.last_activated
                        """,
                        (node_id, ns, ts),
                    )
                for a, b in pairs:
                    conn.execute(
                        """
                        INSERT INTO synapses(
                            node_a, node_b, namespace, weight, activation_count,
                            last_activated, created_at
                        ) VALUES (?, ?, ?, ?, 1, ?, ?)
                        ON CONFLICT(node_a, node_b, namespace) DO UPDATE SET
                            weight = MIN(?, synapses.weight + ?),
                            activation_count = synapses.activation_count + 1,
                            last_activated = excluded.last_activated
                        """,
                        (a, b, ns, min(WEIGHT_CAP, delta), ts, ts, WEIGHT_CAP, delta),
                    )
                conn.execute("COMMIT")
            except Exception:
                conn.execute("ROLLBACK")
                raise

        if pairs:
            # Best-effort: never let the graph-view stream break a real write.
            try:
                from .event_bus import publish as _publish

                _publish(
                    "synapse",
                    {
                        "nodes": list(ids),
                        "pair_count": len(pairs),
                        "strength": float(strength),
                        "namespace": ns,
                    },
                )
            except Exception:
                pass

        return len(pairs)

    def record_sequence(
        self,
        ordered_ids: Iterable[str],
        strength: float = 1.0,
        now: float | None = None,
        namespace: str | None = None,
    ) -> int:
        """Record an ordered sequence as directional transitions.

        For each consecutive distinct pair ``(a, b)`` in ``ordered_ids``,
        bump the ``a -> b`` transition weight. Self-transitions are
        skipped; consecutive duplicates are collapsed.

        Returns the number of transition rows touched. ``ordered_ids``
        may contain any string keys — node ids, file paths, route names,
        etc. The store doesn't care; callers pick the granularity. Writes
        land in ``namespace`` (default: the store's active namespace).
        """
        ids = [n for n in ordered_ids if n]
        if len(ids) < 2:
            return 0

        ns = normalize_namespace(namespace) if namespace else self.namespace
        ts = now if now is not None else time.time()
        delta = TRANSITION_LEARNING_RATE * max(0.0, min(strength, 5.0))

        pairs: list[tuple[str, str]] = []
        prev = ids[0]
        for nxt in ids[1:]:
            if nxt != prev:
                pairs.append((prev, nxt))
                prev = nxt
        if not pairs:
            return 0

        with self._connect() as conn:
            conn.execute("BEGIN")
            try:
                for a, b in pairs:
                    conn.execute(
                        """
                        INSERT INTO synapse_transitions(
                            from_node, to_node, namespace, weight, count,
                            last_activated, created_at
                        ) VALUES (?, ?, ?, ?, 1, ?, ?)
                        ON CONFLICT(from_node, to_node, namespace) DO UPDATE SET
                            weight = MIN(?, synapse_transitions.weight + ?),
                            count = synapse_transitions.count + 1,
                            last_activated = excluded.last_activated
                        """,
                        (
                            a,
                            b,
                            ns,
                            min(TRANSITION_WEIGHT_CAP, delta),
                            ts,
                            ts,
                            TRANSITION_WEIGHT_CAP,
                            delta,
                        ),
                    )
                conn.execute("COMMIT")
            except Exception:
                conn.execute("ROLLBACK")
                raise

        try:
            from .event_bus import publish as _publish

            _publish(
                "transition",
                {
                    "pairs": [[a, b] for a, b in pairs],
                    "count": len(pairs),
                    "strength": float(strength),
                    "namespace": ns,
                },
            )
        except Exception:
            pass

        return len(pairs)

    # ----------------------------------------------------------------- #
    # Decay / retention
    # ----------------------------------------------------------------- #

    def decay(self, now: float | None = None) -> dict:
        """Multiplicatively shrink all weights, honoring per-namespace policy.

        Default namespaces (personal, branch:*, custom): LTP edges
        (activation_count >= LTP_THRESHOLD) decay at LTP_DECAY_RATE and are
        floored at LTP_FLOOR; non-LTP edges decay at DECAY_RATE and are
        pruned below PRUNE_THRESHOLD. ``shared`` decays at the sticky
        SHARED_DECAY_RATE (LTP floor still applies). ``ephemeral`` decays at
        the fast EPHEMERAL_DECAY_RATE with no LTP exemption — session
        scratch is meant to fade. Transitions follow the same policy with
        the TRANSITION_* counterparts. Returns counts of decayed and pruned
        for both signals.
        """
        ts = now if now is not None else time.time()
        special = (SHARED_NAMESPACE, EPHEMERAL_NAMESPACE)
        with self._connect() as conn:
            conn.execute("BEGIN")
            try:
                pruned = 0
                # ephemeral: fast decay, no LTP floor, prune regardless of count.
                conn.execute(
                    "UPDATE synapses SET weight = weight * (1.0 - ?) WHERE namespace = ?",
                    (EPHEMERAL_DECAY_RATE, EPHEMERAL_NAMESPACE),
                )
                cur = conn.execute(
                    "DELETE FROM synapses WHERE namespace = ? AND weight < ?",
                    (EPHEMERAL_NAMESPACE, PRUNE_THRESHOLD),
                )
                pruned += cur.rowcount
                # shared: sticky decay; LTP floor still honored.
                conn.execute(
                    """
                    UPDATE synapses
                    SET weight = MAX(?, weight * (1.0 - ?))
                    WHERE namespace = ? AND activation_count >= ?
                    """,
                    (LTP_FLOOR, SHARED_DECAY_RATE, SHARED_NAMESPACE, LTP_THRESHOLD),
                )
                conn.execute(
                    """
                    UPDATE synapses
                    SET weight = weight * (1.0 - ?)
                    WHERE namespace = ? AND activation_count < ?
                    """,
                    (SHARED_DECAY_RATE, SHARED_NAMESPACE, LTP_THRESHOLD),
                )
                cur = conn.execute(
                    "DELETE FROM synapses WHERE namespace = ? AND weight < ? "
                    "AND activation_count < ?",
                    (SHARED_NAMESPACE, PRUNE_THRESHOLD, LTP_THRESHOLD),
                )
                pruned += cur.rowcount
                # default policy: personal, branch:*, and any custom namespace.
                conn.execute(
                    """
                    UPDATE synapses
                    SET weight = MAX(?, weight * (1.0 - ?))
                    WHERE namespace NOT IN (?, ?) AND activation_count >= ?
                    """,
                    (LTP_FLOOR, LTP_DECAY_RATE, *special, LTP_THRESHOLD),
                )
                conn.execute(
                    """
                    UPDATE synapses
                    SET weight = weight * (1.0 - ?)
                    WHERE namespace NOT IN (?, ?) AND activation_count < ?
                    """,
                    (DECAY_RATE, *special, LTP_THRESHOLD),
                )
                cur = conn.execute(
                    "DELETE FROM synapses WHERE namespace NOT IN (?, ?) AND weight < ? "
                    "AND activation_count < ?",
                    (*special, PRUNE_THRESHOLD, LTP_THRESHOLD),
                )
                pruned += cur.rowcount

                pruned_transitions = 0
                conn.execute(
                    "UPDATE synapse_transitions SET weight = weight * (1.0 - ?) "
                    "WHERE namespace = ?",
                    (EPHEMERAL_TRANSITION_DECAY_RATE, EPHEMERAL_NAMESPACE),
                )
                conn.execute(
                    "UPDATE synapse_transitions SET weight = weight * (1.0 - ?) "
                    "WHERE namespace = ?",
                    (SHARED_TRANSITION_DECAY_RATE, SHARED_NAMESPACE),
                )
                conn.execute(
                    "UPDATE synapse_transitions SET weight = weight * (1.0 - ?) "
                    "WHERE namespace NOT IN (?, ?)",
                    (TRANSITION_DECAY_RATE, *special),
                )
                cur = conn.execute(
                    "DELETE FROM synapse_transitions WHERE weight < ?",
                    (TRANSITION_PRUNE_THRESHOLD,),
                )
                pruned_transitions += cur.rowcount
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
            cur = conn.execute("SELECT COUNT(*) FROM synapse_transitions")
            remaining_transitions = cur.fetchone()[0]
        return {
            "pruned": pruned,
            "remaining": remaining,
            "pruned_transitions": pruned_transitions,
            "remaining_transitions": remaining_transitions,
        }

    # ----------------------------------------------------------------- #
    # Reads
    # ----------------------------------------------------------------- #

    def neighbors(
        self, node_id: str, k: int = 5, namespaces: list[str] | None = None
    ) -> list[tuple[str, float]]:
        """Return the strongest neighbors of a single node.

        Merged across namespaces by default (see MERGED-READ WEIGHTING);
        pass ``namespaces=[...]`` to read specific namespaces raw.
        """
        selected = self._read_namespaces(namespaces)
        if not selected:
            return []
        factors = dict(selected)
        marks = ",".join("?" for _ in selected)
        with self._connect() as conn:
            cur = conn.execute(
                f"""
                SELECT CASE WHEN node_a = ? THEN node_b ELSE node_a END AS other,
                       namespace, weight
                FROM synapses
                WHERE (node_a = ? OR node_b = ?) AND namespace IN ({marks})
                """,
                (node_id, node_id, node_id, *factors),
            )
            merged: dict[str, float] = {}
            for other, ns, weight in cur.fetchall():
                merged[other] = merged.get(other, 0.0) + float(weight) * factors[ns]
        ranked = sorted(merged.items(), key=lambda x: x[1], reverse=True)
        return ranked[:k]

    def next_likely(
        self,
        from_node: str,
        top_k: int = DEFAULT_NEXT_TOP_K,
        namespaces: list[str] | None = None,
    ) -> list[tuple[str, float]]:
        """Return the most likely successors of ``from_node`` as
        ``(to_node, probability)`` pairs.

        Probabilities are normalized over all outgoing transitions from
        ``from_node`` in the selected namespaces (merged default — see
        MERGED-READ WEIGHTING) and sum to 1.0 across the full distribution
        (the returned ``top_k`` may sum to less). Returns an empty list
        when the node has no recorded transitions yet.
        """
        if top_k <= 0:
            return []
        selected = self._read_namespaces(namespaces)
        if not selected:
            return []
        factors = dict(selected)
        marks = ",".join("?" for _ in selected)
        with self._connect() as conn:
            cur = conn.execute(
                f"""
                SELECT to_node, namespace, weight FROM synapse_transitions
                WHERE from_node = ? AND namespace IN ({marks})
                """,
                (from_node, *factors),
            )
            merged: dict[str, float] = {}
            for to_node, ns, weight in cur.fetchall():
                merged[to_node] = merged.get(to_node, 0.0) + float(weight) * factors[ns]
        total = sum(merged.values())
        if total <= 0.0:
            return []
        ranked = sorted(merged.items(), key=lambda x: x[1], reverse=True)[:top_k]
        return [(to_node, weight / total) for to_node, weight in ranked]

    def transitions(
        self,
        from_node: str | None = None,
        min_weight: float = 0.0,
        limit: int = 2000,
        namespaces: list[str] | None = None,
    ) -> list[tuple[str, str, float, int]]:
        """Return transition edges as ``(from_node, to_node, weight, count)``.

        Filters by ``from_node`` when provided. Strongest first. Weights
        merge across the selected namespaces (merged default; explicit
        ``namespaces`` read raw); counts sum. Used by the graph-view UI to
        overlay directional edges and by callers that want raw counts
        rather than normalized probabilities.
        """
        selected = self._read_namespaces(namespaces)
        if not selected:
            return []
        factors = dict(selected)
        marks = ",".join("?" for _ in selected)
        where = f"namespace IN ({marks})"
        params: list = list(factors)
        if from_node is not None:
            where += " AND from_node = ?"
            params.append(from_node)
        with self._connect() as conn:
            cur = conn.execute(
                f"""
                SELECT from_node, to_node, namespace, weight, count
                FROM synapse_transitions
                WHERE {where}
                """,
                params,
            )
            merged: dict[tuple[str, str], list[float]] = {}
            for f, t, ns, weight, count in cur.fetchall():
                entry = merged.setdefault((f, t), [0.0, 0])
                entry[0] += float(weight) * factors[ns]
                entry[1] += int(count)
        rows = [(f, t, w, int(c)) for (f, t), (w, c) in merged.items() if w >= min_weight]
        rows.sort(key=lambda r: r[2], reverse=True)
        return rows[:limit]

    def spread(
        self,
        seeds: Iterable[tuple[str, float]] | Iterable[str],
        depth: int = DEFAULT_SPREAD_DEPTH,
        top_k: int = DEFAULT_SPREAD_TOP_K,
        namespaces: list[str] | None = None,
    ) -> list[tuple[str, float]]:
        """Spreading activation from a set of seed nodes.

        ``seeds`` may be ``[(node_id, energy), ...]`` or just ``[node_id, ...]``
        (each defaulting to energy 1.0). Activation propagates outward along
        weighted edges, decaying by SPREAD_DECAY each hop, with hub
        normalization to prevent runaway central nodes. Edge weights merge
        across the selected namespaces (merged default — see MERGED-READ
        WEIGHTING).

        Returns the top_k nodes (excluding seeds) ranked by accumulated
        activation. Empty list if the graph has no relevant edges yet.
        """
        ranked, _ = self._spread(seeds, depth, top_k, namespaces, track_contributions=False)
        return ranked

    def spread_with_contributions(
        self,
        seeds: Iterable[tuple[str, float]] | Iterable[str],
        depth: int = DEFAULT_SPREAD_DEPTH,
        top_k: int = DEFAULT_SPREAD_TOP_K,
        namespaces: list[str] | None = None,
    ) -> tuple[list[tuple[str, float]], dict[str, dict[str, float]]]:
        """Like :meth:`spread`, but also report per-namespace attribution.

        Returns ``(ranked, contributions)`` where ``contributions`` maps each
        ranked node id to ``{namespace: energy}`` — how much of its activation
        arrived through each namespace's edges (post-multiplier, so the
        shares explain exactly the merged energies). Feeds the PRD 3 trace's
        ``namespace_contribution`` field; costs one extra dict per hop, so
        only the traced recall path uses it.
        """
        return self._spread(seeds, depth, top_k, namespaces, track_contributions=True)

    def _spread(
        self,
        seeds: Iterable[tuple[str, float]] | Iterable[str],
        depth: int,
        top_k: int,
        namespaces: list[str] | None,
        track_contributions: bool,
    ) -> tuple[list[tuple[str, float]], dict[str, dict[str, float]]]:
        seed_list: list[tuple[str, float]] = []
        for s in seeds:
            if isinstance(s, tuple):
                node_id, energy = s
                seed_list.append((node_id, float(energy)))
            else:
                seed_list.append((str(s), 1.0))
        if not seed_list:
            return [], {}
        selected = self._read_namespaces(namespaces)
        if not selected:
            return [], {}
        factors = dict(selected)
        marks = ",".join("?" for _ in selected)

        activation: dict[str, float] = {}
        for node_id, energy in seed_list:
            activation[node_id] = activation.get(node_id, 0.0) + energy

        seed_ids = {nid for nid, _ in seed_list}
        frontier: dict[str, float] = dict(activation)
        contributions: dict[str, dict[str, float]] = {}

        with self._connect() as conn:
            for _hop in range(depth):
                if not frontier:
                    break
                next_frontier: dict[str, float] = {}
                for node_id, energy in frontier.items():
                    if energy <= 0.0:
                        continue
                    cur = conn.execute(
                        f"""
                        SELECT CASE WHEN node_a = ? THEN node_b ELSE node_a END AS other,
                               namespace, weight
                        FROM synapses
                        WHERE (node_a = ? OR node_b = ?) AND namespace IN ({marks})
                        """,
                        (node_id, node_id, node_id, *factors),
                    )
                    rows = cur.fetchall()
                    if not rows:
                        continue
                    # Merge each neighbor's per-namespace weights, remembering
                    # the per-namespace share when attribution is requested.
                    edge_weights: dict[str, float] = {}
                    edge_shares: dict[str, dict[str, float]] = {}
                    for other, ns, weight in rows:
                        share = float(weight) * factors[ns]
                        edge_weights[other] = edge_weights.get(other, 0.0) + share
                        if track_contributions:
                            by_ns = edge_shares.setdefault(other, {})
                            by_ns[ns] = by_ns.get(ns, 0.0) + share
                    degree = len(edge_weights)
                    hub_factor = math.sqrt(HUB_DEGREE / degree) if degree > HUB_DEGREE else 1.0
                    for other, merged_weight in edge_weights.items():
                        propagated = energy * merged_weight * SPREAD_DECAY * hub_factor
                        if propagated <= 0.0:
                            continue
                        activation[other] = activation.get(other, 0.0) + propagated
                        next_frontier[other] = next_frontier.get(other, 0.0) + propagated
                        if track_contributions:
                            target = contributions.setdefault(other, {})
                            scale = energy * SPREAD_DECAY * hub_factor
                            for ns, share in edge_shares[other].items():
                                target[ns] = target.get(ns, 0.0) + share * scale
                frontier = next_frontier

        for sid in seed_ids:
            activation.pop(sid, None)
            contributions.pop(sid, None)

        ranked = sorted(activation.items(), key=lambda x: x[1], reverse=True)[:top_k]
        if not track_contributions:
            return ranked, {}
        ranked_ids = {nid for nid, _ in ranked}
        return ranked, {nid: by_ns for nid, by_ns in contributions.items() if nid in ranked_ids}

    def edges(
        self,
        min_weight: float = 0.0,
        limit: int = 2000,
        namespaces: list[str] | None = None,
    ) -> list[tuple[str, str, float, int]]:
        """Return synapse edges as (node_a, node_b, weight, activation_count).

        Strongest first. Weights merge across the selected namespaces
        (merged default; explicit ``namespaces`` read raw); activation
        counts sum. Used by the graph-view UI to overlay learned
        associations on top of the structural code graph, and is a
        convenient read-only view for inspection and export.
        """
        selected = self._read_namespaces(namespaces)
        if not selected:
            return []
        factors = dict(selected)
        marks = ",".join("?" for _ in selected)
        with self._connect() as conn:
            cur = conn.execute(
                f"""
                SELECT node_a, node_b, namespace, weight, activation_count
                FROM synapses
                WHERE namespace IN ({marks})
                """,
                list(factors),
            )
            merged: dict[tuple[str, str], list[float]] = {}
            for a, b, ns, weight, count in cur.fetchall():
                entry = merged.setdefault((a, b), [0.0, 0])
                entry[0] += float(weight) * factors[ns]
                entry[1] += int(count)
        rows = [(a, b, w, int(c)) for (a, b), (w, c) in merged.items() if w >= min_weight]
        rows.sort(key=lambda r: r[2], reverse=True)
        return rows[:limit]

    def normalize_hubs(self, max_degree: int = HUB_DEGREE) -> int:
        """Trim weights on nodes that have grown into runaway hubs.

        For every (node, namespace) with degree > max_degree within that
        namespace, scale its incident edges by sqrt(max_degree / degree).
        Returns the number of (node, namespace) pairs adjusted.
        """
        with self._connect() as conn:
            cur = conn.execute(
                """
                SELECT node_id, namespace, COUNT(*) AS degree FROM (
                    SELECT node_a AS node_id, namespace FROM synapses
                    UNION ALL
                    SELECT node_b AS node_id, namespace FROM synapses
                )
                GROUP BY node_id, namespace
                HAVING degree > ?
                """,
                (max_degree,),
            )
            hubs = cur.fetchall()
            if not hubs:
                return 0
            conn.execute("BEGIN")
            try:
                for node_id, ns, degree in hubs:
                    factor = math.sqrt(max_degree / degree)
                    conn.execute(
                        """
                        UPDATE synapses
                        SET weight = weight * ?
                        WHERE (node_a = ? OR node_b = ?) AND namespace = ?
                        """,
                        (factor, node_id, node_id, ns),
                    )
                conn.execute("COMMIT")
            except Exception:
                conn.execute("ROLLBACK")
                raise
        return len(hubs)

    # ----------------------------------------------------------------- #
    # Stats / maintenance
    # ----------------------------------------------------------------- #

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
            nodes = conn.execute("SELECT COUNT(DISTINCT node_id) FROM node_activations").fetchone()[
                0
            ]
            top_hubs = conn.execute("""
                SELECT node_id, COUNT(*) AS degree FROM (
                    SELECT node_a AS node_id FROM synapses
                    UNION ALL
                    SELECT node_b AS node_id FROM synapses
                )
                GROUP BY node_id
                ORDER BY degree DESC
                LIMIT 5
                """).fetchall()
            transitions = conn.execute("SELECT COUNT(*) FROM synapse_transitions").fetchone()[0]
            transition_weight = conn.execute(
                "SELECT COALESCE(SUM(weight), 0.0) FROM synapse_transitions"
            ).fetchone()[0]
            by_namespace: dict[str, dict] = {}
            for ns, count, weight in conn.execute(
                "SELECT namespace, COUNT(*), COALESCE(SUM(weight), 0.0) "
                "FROM synapses GROUP BY namespace"
            ).fetchall():
                entry = by_namespace.setdefault(ns, _empty_namespace_stats())
                entry["edges"] = int(count)
                entry["weight"] = round(float(weight), 4)
            for ns, count, weight in conn.execute(
                "SELECT namespace, COUNT(*), COALESCE(SUM(weight), 0.0) "
                "FROM synapse_transitions GROUP BY namespace"
            ).fetchall():
                entry = by_namespace.setdefault(ns, _empty_namespace_stats())
                entry["transitions"] = int(count)
                entry["transition_weight"] = round(float(weight), 4)
            for ns, count in conn.execute(
                "SELECT namespace, COUNT(*) FROM node_activations GROUP BY namespace"
            ).fetchall():
                entry = by_namespace.setdefault(ns, _empty_namespace_stats())
                entry["nodes"] = int(count)
        return {
            "edges": int(edges),
            "ltp_edges": int(ltp_edges),
            "total_weight": float(total_weight),
            "nodes": int(nodes),
            "top_hubs": [(nid, int(deg)) for nid, deg in top_hubs],
            "transitions": int(transitions),
            "transition_weight": float(transition_weight),
            "db_path": str(self.db_path),
            "namespace": self.namespace,
            "schema_version": self.schema_version(),
            "namespaces": by_namespace,
        }

    def clear_namespace(self, namespace: str) -> dict:
        """Delete every row in one namespace, leaving all others intact.

        The surgical reset behind ``neuralmind memory reset --namespace`` and
        the session-boundary ``ephemeral`` cleanup. Returns deletion counts.
        """
        ns = normalize_namespace(namespace)
        with self._connect() as conn:
            conn.execute("BEGIN")
            try:
                edges = conn.execute("DELETE FROM synapses WHERE namespace = ?", (ns,)).rowcount
                transitions = conn.execute(
                    "DELETE FROM synapse_transitions WHERE namespace = ?", (ns,)
                ).rowcount
                activations = conn.execute(
                    "DELETE FROM node_activations WHERE namespace = ?", (ns,)
                ).rowcount
                conn.execute("COMMIT")
            except Exception:
                conn.execute("ROLLBACK")
                raise
        return {
            "namespace": ns,
            "edges": int(edges),
            "transitions": int(transitions),
            "activations": int(activations),
        }

    def reset(self) -> None:
        """Drop all synapses, transitions, and activations. Useful for
        tests and full retrain. The schema version marker survives so the
        store is never mistaken for a pre-namespace database."""
        with self._connect() as conn:
            conn.execute("DELETE FROM synapses")
            conn.execute("DELETE FROM synapse_transitions")
            conn.execute("DELETE FROM node_activations")
            conn.execute("DELETE FROM meta")
            self._stamp_schema_version(conn)

    # ----------------------------------------------------------------- #
    # Import (PRD 4 bundles — see neuralmind.ir for the bundle format)
    # ----------------------------------------------------------------- #

    def import_edges(
        self,
        rows: Iterable[tuple[str, str, float, int]],
        namespace: str,
        now: float | None = None,
    ) -> int:
        """Merge ``(node_a, node_b, weight, activation_count)`` rows into a
        namespace.

        Conflicts keep the MAX of weight and activation count, so importing
        the same bundle twice is idempotent — weights never double. Weights
        are clamped to [0, WEIGHT_CAP]. Returns the number of rows merged.
        """
        ns = normalize_namespace(namespace)
        ts = now if now is not None else time.time()
        merged = 0
        with self._connect() as conn:
            conn.execute("BEGIN")
            try:
                for a, b, weight, count in rows:
                    pair = _canonical(str(a), str(b))
                    if pair is None:
                        continue
                    clamped = max(0.0, min(float(weight), WEIGHT_CAP))
                    conn.execute(
                        """
                        INSERT INTO synapses(
                            node_a, node_b, namespace, weight, activation_count,
                            last_activated, created_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?)
                        ON CONFLICT(node_a, node_b, namespace) DO UPDATE SET
                            weight = MAX(synapses.weight, excluded.weight),
                            activation_count = MAX(
                                synapses.activation_count, excluded.activation_count
                            ),
                            last_activated = excluded.last_activated
                        """,
                        (*pair, ns, clamped, max(0, int(count)), ts, ts),
                    )
                    merged += 1
                conn.execute("COMMIT")
            except Exception:
                conn.execute("ROLLBACK")
                raise
        return merged

    def import_transitions(
        self,
        rows: Iterable[tuple[str, str, float, int]],
        namespace: str,
        now: float | None = None,
    ) -> int:
        """Merge ``(from_node, to_node, weight, count)`` transition rows into
        a namespace. Same MAX-merge idempotency as :meth:`import_edges`."""
        ns = normalize_namespace(namespace)
        ts = now if now is not None else time.time()
        merged = 0
        with self._connect() as conn:
            conn.execute("BEGIN")
            try:
                for a, b, weight, count in rows:
                    if not a or not b or a == b:
                        continue
                    clamped = max(0.0, min(float(weight), TRANSITION_WEIGHT_CAP))
                    conn.execute(
                        """
                        INSERT INTO synapse_transitions(
                            from_node, to_node, namespace, weight, count,
                            last_activated, created_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?)
                        ON CONFLICT(from_node, to_node, namespace) DO UPDATE SET
                            weight = MAX(synapse_transitions.weight, excluded.weight),
                            count = MAX(synapse_transitions.count, excluded.count),
                            last_activated = excluded.last_activated
                        """,
                        (str(a), str(b), ns, clamped, max(0, int(count)), ts, ts),
                    )
                    merged += 1
                conn.execute("COMMIT")
            except Exception:
                conn.execute("ROLLBACK")
                raise
        return merged


def _empty_namespace_stats() -> dict:
    return {"edges": 0, "weight": 0.0, "transitions": 0, "transition_weight": 0.0, "nodes": 0}


def default_db_path(project_path: str | Path) -> Path:
    return Path(project_path) / ".neuralmind" / "synapses.db"
