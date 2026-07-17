"""Tests for the reasoning trace store (PRD 2 A1)."""

from __future__ import annotations

import time

import pytest

from neuralmind.traces import (
    TraceStore,
    _fingerprint,
    ReasoningTrace,
)


class TestFingerprint:
    def test_stable(self):
        assert _fingerprint("How does auth work?") == _fingerprint("How does auth work?")

    def test_unique(self):
        assert _fingerprint("query A") != _fingerprint("query B")

    def test_length(self):
        assert len(_fingerprint("any query")) == 16


class TestTraceStore:
    def test_record_and_query(self, tmp_path):
        store = TraceStore(tmp_path / "test.db")
        store.record(
            "sess-1",
            "How does auth work?",
            strategy="search",
            tools_used=["grep"],
            outcome="success",
            success_signal=0.9,
        )
        traces = store.query(session_id="sess-1")
        assert len(traces) == 1
        assert traces[0].strategy == "search"
        assert traces[0].tools_used == ["grep"]
        assert traces[0].outcome == "success"
        assert traces[0].success_signal == 0.9

    def test_count(self, tmp_path):
        store = TraceStore(tmp_path / "test.db")
        assert store.count() == 0
        store.record("sess-1", "q1")
        store.record("sess-1", "q2")
        assert store.count() == 2

    def test_count_by_session(self, tmp_path):
        store = TraceStore(tmp_path / "test.db")
        store.record("sess-1", "q1")
        store.record("sess-2", "q2")
        assert store.count(session_id="sess-1") == 1
        assert store.count(session_id="sess-2") == 1

    def test_query_by_outcome(self, tmp_path):
        store = TraceStore(tmp_path / "test.db")
        store.record("sess-1", "q1", outcome="success")
        store.record("sess-1", "q2", outcome="failure")
        assert len(store.query(outcome="success")) == 1
        assert len(store.query(outcome="failure")) == 1

    def test_query_by_time_window(self, tmp_path):
        store = TraceStore(tmp_path / "test.db")
        now = time.time()
        store.record("sess-1", "q1", timestamp=now - 100)
        store.record("sess-1", "q2", timestamp=now - 50)
        store.record("sess-1", "q3", timestamp=now)
        traces = store.query(since=now - 60)
        assert len(traces) == 2

    def test_successful_fingerprints(self, tmp_path):
        store = TraceStore(tmp_path / "test.db")
        store.record("sess-1", "good query", success_signal=0.9)
        store.record("sess-1", "bad query", success_signal=0.2)
        fps = store.successful_fingerprints(min_success=0.7)
        assert len(fps) == 1
        assert fps[0] == _fingerprint("good query")

    def test_query_ordering(self, tmp_path):
        store = TraceStore(tmp_path / "test.db")
        store.record("sess-1", "q1", timestamp=100)
        store.record("sess-1", "q2", timestamp=300)
        store.record("sess-1", "q3", timestamp=200)
        traces = store.query(order="desc")
        timestamps = [t.timestamp for t in traces]
        assert timestamps == [300, 200, 100]

    def test_query_limit(self, tmp_path):
        store = TraceStore(tmp_path / "test.db")
        for i in range(10):
            store.record("sess-1", f"q{i}")
        assert len(store.query(limit=3)) == 3

    def test_min_success_filter(self, tmp_path):
        store = TraceStore(tmp_path / "test.db")
        store.record("sess-1", "q1", success_signal=0.9)
        store.record("sess-1", "q2", success_signal=0.5)
        store.record("sess-1", "q3", success_signal=0.8)
        traces = store.query(min_success=0.7)
        assert len(traces) == 2
