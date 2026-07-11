"""Tests for local memory scaffolding."""

from __future__ import annotations

import json


class TestMemoryConsent:
    """Tests for memory consent sentinel behavior."""

    def test_write_and_read_consent(self, monkeypatch, tmp_path):
        """Consent sentinel can be written and read back."""
        from neuralmind import memory

        monkeypatch.setenv("HOME", str(tmp_path))
        monkeypatch.setenv("USERPROFILE", str(tmp_path))

        memory.write_consent_sentinel(True)

        assert memory.read_consent_sentinel() is True
        assert memory.consent_file().exists()

    def test_should_prompt_only_for_tty_without_sentinel(self, monkeypatch, tmp_path):
        """Prompt should only occur in TTY mode when sentinel is absent."""
        from neuralmind import memory

        monkeypatch.setenv("HOME", str(tmp_path))
        monkeypatch.setenv("USERPROFILE", str(tmp_path))
        assert memory.should_prompt_for_consent(is_tty=True) is True
        assert memory.should_prompt_for_consent(is_tty=False) is False


class TestMemoryLogging:
    """Tests for query event logging."""

    def test_log_query_event_writes_project_and_global_jsonl(self, monkeypatch, tmp_path):
        """Memory logging writes JSONL events in both scopes."""
        from neuralmind import memory
        from neuralmind.context_selector import ContextResult, TokenBudget

        project_path = tmp_path / "project"
        project_path.mkdir()
        monkeypatch.setenv("HOME", str(tmp_path))
        monkeypatch.setenv("USERPROFILE", str(tmp_path))

        memory.write_consent_sentinel(True)
        result = ContextResult(
            context="context",
            budget=TokenBudget(l0_identity=10, l1_summary=20),
            layers_used=["L0", "L1"],
            communities_loaded=[1],
            search_hits=3,
            reduction_ratio=5.2,
        )

        logged = memory.log_query_event(project_path, "how auth works", result)
        assert logged is True

        project_events = memory.project_query_events_file(project_path)
        global_events = memory.global_query_events_file()
        assert project_events.exists()
        assert global_events.exists()

        line = project_events.read_text(encoding="utf-8").strip().splitlines()[0]
        payload = json.loads(line)
        assert payload["query"] == "how auth works"
        assert payload["retrieval_summary"]["search_hits"] == 3


class TestQueryEventReading:
    """Tests for reading logged query events."""

    def test_read_query_events_empty_file(self, tmp_path):
        """read_query_events handles missing file gracefully."""
        from neuralmind import memory

        events_file = tmp_path / "nonexistent.jsonl"
        events = memory.read_query_events(events_file)
        assert events == []

    def test_read_query_events_from_jsonl(self, tmp_path):
        """read_query_events loads events from JSONL file."""
        from neuralmind import memory

        events_file = tmp_path / "events.jsonl"
        event1 = {
            "event_type": "query",
            "query": "auth",
            "retrieval_summary": {"communities_loaded": [0, 1]},
        }
        event2 = {
            "event_type": "query",
            "query": "api",
            "retrieval_summary": {"communities_loaded": [1, 2]},
        }
        events_file.write_text(f"{json.dumps(event1)}\n{json.dumps(event2)}\n", encoding="utf-8")

        events = memory.read_query_events(events_file)
        assert len(events) == 2
        assert events[0]["query"] == "auth"
        assert events[1]["query"] == "api"

    def test_read_query_events_skips_invalid_lines(self, tmp_path):
        """read_query_events skips invalid JSON lines."""
        from neuralmind import memory

        events_file = tmp_path / "events.jsonl"
        event = {"event_type": "query", "query": "test"}
        events_file.write_text(
            f"{json.dumps(event)}\ninvalid json\n{json.dumps(event)}\n",
            encoding="utf-8",
        )

        events = memory.read_query_events(events_file)
        assert len(events) == 2


class TestSessionIdAndWakeup:
    """D1 logging substrate: session_id on events + wakeup-event logging."""

    def _result(self):
        from neuralmind.context_selector import ContextResult, TokenBudget

        return ContextResult(
            context="ctx",
            budget=TokenBudget(l0_identity=10, l1_summary=20),
            layers_used=["L0:Identity", "L1:Summary"],
            communities_loaded=[1],
            search_hits=2,
            reduction_ratio=4.0,
        )

    def test_query_event_carries_session_id(self, monkeypatch, tmp_path):
        from neuralmind import memory

        monkeypatch.setenv("HOME", str(tmp_path))
        monkeypatch.setenv("USERPROFILE", str(tmp_path))
        monkeypatch.setenv("CLAUDE_SESSION_ID", "sess-123")
        memory.write_consent_sentinel(True)

        project = tmp_path / "project"
        project.mkdir()
        assert memory.log_query_event(project, "q", self._result()) is True

        line = (
            memory.project_query_events_file(project)
            .read_text(encoding="utf-8")
            .strip()
            .splitlines()[0]
        )
        payload = json.loads(line)
        assert payload["session_id"] == "sess-123"

    def test_session_id_falls_back_to_stable_process_uuid(self, monkeypatch):
        from neuralmind import memory

        monkeypatch.delenv("CLAUDE_SESSION_ID", raising=False)
        # Reset the lazily-cached process id so we observe a fresh generation.
        monkeypatch.setattr(memory, "_PROCESS_SESSION_ID", None)
        first = memory._current_session_id()
        second = memory._current_session_id()
        assert first == second  # stable within the process
        assert len(first) > 0

    def test_log_wakeup_event_writes_both_scopes(self, monkeypatch, tmp_path):
        from neuralmind import memory

        monkeypatch.setenv("HOME", str(tmp_path))
        monkeypatch.setenv("USERPROFILE", str(tmp_path))
        monkeypatch.setenv("CLAUDE_SESSION_ID", "wake-1")
        memory.write_consent_sentinel(True)

        project = tmp_path / "project"
        project.mkdir()
        assert memory.log_wakeup_event(project, self._result()) is True

        project_events = memory.project_query_events_file(project)
        global_events = memory.global_query_events_file()
        assert project_events.exists()
        assert global_events.exists()

        payload = json.loads(project_events.read_text(encoding="utf-8").strip().splitlines()[0])
        assert payload["event_type"] == "wakeup"
        assert payload["session_id"] == "wake-1"
        assert "query" not in payload

    def test_wakeup_event_skipped_without_consent(self, monkeypatch, tmp_path):
        from neuralmind import memory

        monkeypatch.setenv("HOME", str(tmp_path))
        monkeypatch.setenv("USERPROFILE", str(tmp_path))
        # No consent sentinel written → logging disabled.
        project = tmp_path / "project"
        project.mkdir()
        assert memory.log_wakeup_event(project, self._result()) is False
        assert not memory.project_query_events_file(project).exists()


class TestAggregationHelpers:
    """D1 read-side aggregation primitives subsystem A consumes."""

    def _q(self, sid, communities, *, layers=None, ts="2026-05-07T00:00:00+00:00"):
        return {
            "event_type": "query",
            "timestamp": ts,
            "session_id": sid,
            "retrieval_summary": {
                "layers_used": layers or ["L0:Identity", "L1:Summary"],
                "communities_loaded": list(communities),
            },
        }

    def _w(self, sid, ts="2026-05-07T00:00:00+00:00"):
        return {
            "event_type": "wakeup",
            "timestamp": ts,
            "session_id": sid,
            "retrieval_summary": {"layers_used": ["L0:Identity", "L1:Summary"]},
        }

    def test_read_events_returns_both_event_types(self, tmp_path):
        from neuralmind import memory

        path = tmp_path / "events.jsonl"
        path.write_text(
            json.dumps(self._q("s", [1])) + "\n" + json.dumps(self._w("s")) + "\n",
            encoding="utf-8",
        )
        events = memory.read_events(path)
        assert {e["event_type"] for e in events} == {"query", "wakeup"}

    def test_recent_events_windows_by_timestamp_and_count(self):
        from neuralmind import memory

        events = [
            self._q("s", [1], ts="2026-01-01T00:00:00+00:00"),
            self._q("s", [1], ts="2026-06-01T00:00:00+00:00"),
            self._q("s", [1], ts="2026-06-02T00:00:00+00:00"),
        ]
        windowed = memory.recent_events(events, since_ts="2026-05-01T00:00:00+00:00")
        assert len(windowed) == 2
        last_one = memory.recent_events(events, last_n=1)
        assert last_one == events[-1:]

    def test_escalation_rate_matches_l3_layer_exactly(self):
        from neuralmind import memory

        escalated = self._q("s", [1], layers=["L0:Identity", "L3:Search(4 results)"])
        plain = self._q("s", [1], layers=["L0:Identity", "L1:Summary"])
        # "L30" must not false-match the L3 layer.
        false_match = self._q("s", [1], layers=["L30:Something"])
        assert memory.escalation_rate([escalated, plain]) == 0.5
        assert memory.escalation_rate([false_match]) == 0.0
        assert memory.escalation_rate([]) == 0.0

    def test_re_query_rate_consecutive_overlap(self):
        from neuralmind import memory

        # Two same-session queries with identical communities → full overlap.
        high = [self._q("s", [1, 2]), self._q("s", [1, 2])]
        assert memory.re_query_rate(high) == 1.0
        # Disjoint communities → no overlap.
        low = [self._q("s", [1]), self._q("s", [2])]
        assert memory.re_query_rate(low) == 0.0

    def test_re_query_rate_skips_sessionless_and_empty_community_pairs(self):
        from neuralmind import memory

        # Pre-D1 events (no session_id) are skipped entirely → no pairs.
        sessionless = [
            {"event_type": "query", "retrieval_summary": {"communities_loaded": [1]}},
            {"event_type": "query", "retrieval_summary": {"communities_loaded": [1]}},
        ]
        assert memory.re_query_rate(sessionless) == 0.0
        # A pair where one query loaded no communities carries no signal.
        empty_pair = [self._q("s", []), self._q("s", [1])]
        assert memory.re_query_rate(empty_pair) == 0.0

    def test_wakeup_only_rate(self):
        from neuralmind import memory

        events = [
            self._w("only-wakeup"),  # wakeup, no query → counts
            self._w("woke-then-queried"),
            self._q("woke-then-queried", [1]),  # had a follow-up → doesn't count
        ]
        # 1 of 2 wakeup-bearing sessions was wakeup-only.
        assert memory.wakeup_only_rate(events) == 0.5
        # No wakeups at all → not eligible → 0.0.
        assert memory.wakeup_only_rate([self._q("s", [1])]) == 0.0
