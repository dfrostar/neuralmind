"""`neuralmind cognition-loop` — an idempotent maintenance pass, not a wipe.

stdlib-only (SQLite), like the rest of the synapse-layer tests.

Before v4.6 the pass ran its own SQL: a linear decay applied to every
namespace up to nine times per run (an edge idle for ~2 days was deleted), a
replay of recent queries into a `traversal` namespace, LTP promotion without
repeated use, and deletion of session summaries. These tests pin the
replacement: the store's own half-life decay plus read-dedup cleanup.
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path

import pytest

from neuralmind.cognition_loop import run_cognition_loop
from neuralmind.read_dedup import ReadCache, read_cache_path
from neuralmind.synapses import DEFAULT_NAMESPACE, SHARED_NAMESPACE, SynapseStore, default_db_path

DAY = 86400.0


@pytest.fixture(autouse=True)
def _learning_on(monkeypatch):
    monkeypatch.delenv("NEURALMIND_NO_LEARN", raising=False)


def _store(project: Path) -> SynapseStore:
    return SynapseStore(default_db_path(project))


def _weight(store: SynapseStore, a: str, b: str, namespace: str) -> float | None:
    for x, y, w, _c in store.edges(namespaces=[namespace]):
        if {x, y} == {a, b}:
            return w
    return None


def test_project_without_memory_is_skipped_and_untouched(tmp_path):
    report = run_cognition_loop(tmp_path)
    assert report.skipped == "no learned memory yet"
    assert not default_db_path(tmp_path).exists()


def test_no_learn_skips(tmp_path, monkeypatch):
    _store(tmp_path).reinforce(["a.py", "b.py"])
    monkeypatch.setenv("NEURALMIND_NO_LEARN", "1")
    assert run_cognition_loop(tmp_path).skipped == "NEURALMIND_NO_LEARN=1"


def test_recently_idle_edges_survive(tmp_path):
    """The old pass deleted every non-LTP edge idle for more than ~1.7 days."""
    store = _store(tmp_path)
    three_days_ago = time.time() - 3 * DAY
    store.reinforce(["auth.py", "session.py"], now=three_days_ago)
    store.import_edges(
        [("api.py", "models.py", 0.6, 2)], namespace=SHARED_NAMESPACE, now=three_days_ago
    )

    report = run_cognition_loop(tmp_path)

    assert report.skipped == ""
    personal = _weight(store, "auth.py", "session.py", DEFAULT_NAMESPACE)
    shared = _weight(store, "api.py", "models.py", SHARED_NAMESPACE)
    # Half-life decay, not deletion. A reinforced personal edge carries a
    # learned half-life of at least 3 days (learned_decay), so 3 idle days
    # leave at least half of its 0.30; imported shared edges use the 60-day
    # team half-life (×0.966).
    assert personal is not None and 0.14 < personal < 0.30
    assert shared is not None and 0.57 < shared < 0.60


def test_running_twice_does_not_decay_twice(tmp_path):
    store = _store(tmp_path)
    store.reinforce(["auth.py", "session.py"], now=time.time() - 10 * DAY)
    run_cognition_loop(tmp_path)
    after_first = _weight(store, "auth.py", "session.py", DEFAULT_NAMESPACE)
    run_cognition_loop(tmp_path)
    after_second = _weight(store, "auth.py", "session.py", DEFAULT_NAMESPACE)
    assert after_first is not None
    assert after_second == pytest.approx(after_first, rel=1e-4)


def test_session_summaries_are_left_alone(tmp_path):
    _store(tmp_path).reinforce(["a.py", "b.py"])
    summaries = tmp_path / ".neuralmind" / "summaries"
    summaries.mkdir(parents=True)
    old = summaries / "2026-06-01.md"
    old.write_text("# old session\n")
    sixty_days_ago = time.time() - 60 * DAY
    os.utime(old, (sixty_days_ago, sixty_days_ago))
    run_cognition_loop(tmp_path)
    assert old.exists()


def test_recent_queries_are_not_replayed_into_a_traversal_namespace(tmp_path):
    store = _store(tmp_path)
    store.reinforce(["a.py", "b.py"])
    log = tmp_path / ".neuralmind" / "recent_queries.jsonl"
    hits = [{"id": f"node_{i}", "label": f"n{i}"} for i in range(4)]
    log.write_text("\n".join(json.dumps({"top_hits": hits}) for _ in range(5)) + "\n")
    run_cognition_loop(tmp_path)
    assert "traversal" not in store.stats().get("namespaces", {})
    assert not store.edges(namespaces=["traversal"])


def test_read_dedup_rows_are_pruned(tmp_path):
    _store(tmp_path).reinforce(["a.py", "b.py"])
    cache = ReadCache(tmp_path)
    cache.observe("old-session", "", "/a.py", "", "h", now=0.0)
    cache.observe("live-session", "", "/a.py", "", "h")
    report = run_cognition_loop(tmp_path)
    assert report.read_cache_pruned == 1
    assert cache.stats()["sessions"] == 1


def test_read_cache_is_not_created(tmp_path):
    _store(tmp_path).reinforce(["a.py", "b.py"])
    run_cognition_loop(tmp_path)
    assert not read_cache_path(tmp_path).exists()


def test_cli_json(tmp_path, capsys):
    from neuralmind.cli import build_parser

    _store(tmp_path).reinforce(["a.py", "b.py"])
    args = build_parser().parse_args(["cognition-loop", str(tmp_path), "--json"])
    args.func(args)
    report = json.loads(capsys.readouterr().out)
    assert report["skipped"] == ""
    assert report["edges_remaining"] == 1
    assert {"edges_pruned", "transitions_pruned", "read_cache_pruned", "duration_secs"} <= set(
        report
    )


def test_cli_text_when_there_is_nothing_to_do(tmp_path, capsys):
    from neuralmind.cli import build_parser

    args = build_parser().parse_args(["cognition-loop", str(tmp_path)])
    args.func(args)
    assert "Nothing to do: no learned memory yet." in capsys.readouterr().out
