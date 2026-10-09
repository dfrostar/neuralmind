"""The synapse read paths look a node's edges up by node, not by namespace.

Without table statistics SQLite chose the namespace index for any query with a
namespace predicate, so ``spread()`` scanned every edge in the namespace once
per frontier node. The latency gate's store is too small to show it; on this
repository's 28.8k-edge store it was 70 ms of a 74 ms query, and up to 490 ms
when the frontier reached a hub. These tests capture the SQL each read path
runs and ask SQLite how it plans it, so a rewrite of the query that loses the
node indexes fails here instead of in a user's prompt latency.

Stdlib-only, like the rest of the synapse layer's tests.
"""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager

import pytest

from neuralmind.synapses import SynapseStore


@pytest.fixture
def store(tmp_path):
    s = SynapseStore(tmp_path / "synapses.db")
    for i in range(30):
        s.reinforce([f"n{i}", f"n{i + 1}", "hub"])
    return s


def _captured_selects(store, monkeypatch, call):
    """Run ``call`` and return every SELECT it sent that names a node column."""
    statements: list[str] = []
    original = store._connect

    @contextmanager
    def tracing():
        with original() as conn:
            conn.set_trace_callback(statements.append)
            yield conn

    monkeypatch.setattr(store, "_connect", tracing)
    call()
    return [
        sql
        for sql in statements
        if sql.lstrip().upper().startswith("SELECT") and ("node_a" in sql or "node_b" in sql)
    ]


def _plan(store, sql: str) -> str:
    with sqlite3.connect(store.db_path) as conn:
        return " | ".join(row[-1] for row in conn.execute("EXPLAIN QUERY PLAN " + sql))


@pytest.mark.parametrize(
    "name,call",
    [
        ("spread", lambda s: s.spread(["n3"], depth=2)),
        ("neighbors", lambda s: s.neighbors("hub")),
        ("degrees", lambda s: s.degrees(["hub", "n3"])),
    ],
)
def test_node_lookups_use_the_node_indexes(store, monkeypatch, name, call):
    selects = _captured_selects(store, monkeypatch, lambda: call(store))
    assert selects, f"{name} ran no node lookup"
    for sql in selects:
        plan = _plan(store, sql)
        assert "idx_syn_ns" not in plan, f"{name} scans by namespace: {plan}\n{sql}"
        assert "node_a=?" in plan or "node_b=?" in plan, f"{name}: {plan}\n{sql}"


def test_the_namespace_index_would_have_been_chosen(store):
    # The tripwire is live: the same lookup without the unary `+` still plans
    # onto the namespace index on this SQLite, which is the regression above.
    sql = (
        "SELECT node_b FROM synapses "
        "WHERE (node_a = 'hub' OR node_b = 'hub') AND namespace IN ('shared')"
    )
    assert "idx_syn_ns" in _plan(store, sql)
