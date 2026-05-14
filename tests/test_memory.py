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


class TestSessionId:
    """Tests for session id resolution used by event logging."""

    def test_session_id_honors_claude_session_env(self, monkeypatch):
        from neuralmind import memory

        monkeypatch.setenv("CLAUDE_SESSION_ID", "abc-123")
        assert memory._current_session_id() == "abc-123"

    def test_session_id_falls_back_to_stable_process_uuid(self, monkeypatch):
        from neuralmind import memory

        monkeypatch.delenv("CLAUDE_SESSION_ID", raising=False)
        monkeypatch.setattr(memory, "_PROCESS_SESSION_ID", None)
        first = memory._current_session_id()
        second = memory._current_session_id()
        assert first == second
        assert len(first) > 0


class TestWakeupLogging:
    """Tests for wakeup event logging."""

    def _result(self):
        from neuralmind.context_selector import ContextResult, TokenBudget

        return ContextResult(
            context="ctx",
            budget=TokenBudget(l0_identity=10, l1_summary=20),
            layers_used=["L0", "L1"],
            communities_loaded=[],
            search_hits=0,
            reduction_ratio=0.0,
        )

    def test_log_wakeup_event_writes_project_and_global_jsonl(self, monkeypatch, tmp_path):
        from neuralmind import memory

        project_path = tmp_path / "project"
        project_path.mkdir()
        monkeypatch.setenv("HOME", str(tmp_path))
        monkeypatch.setenv("USERPROFILE", str(tmp_path))
        monkeypatch.setenv("CLAUDE_SESSION_ID", "session-1")
        memory.write_consent_sentinel(True)

        logged = memory.log_wakeup_event(project_path, self._result())
        assert logged is True

        line = (
            memory.project_query_events_file(project_path)
            .read_text(encoding="utf-8")
            .strip()
            .splitlines()[0]
        )
        payload = json.loads(line)
        assert payload["event_type"] == "wakeup"
        assert payload["session_id"] == "session-1"
        assert payload["retrieval_summary"]["layers_used"] == ["L0", "L1"]
        assert "query" not in payload

    def test_log_wakeup_event_without_consent_is_noop(self, monkeypatch, tmp_path):
        from neuralmind import memory

        project_path = tmp_path / "project"
        project_path.mkdir()
        monkeypatch.setenv("HOME", str(tmp_path))
        monkeypatch.setenv("USERPROFILE", str(tmp_path))
        # No consent written.

        assert memory.log_wakeup_event(project_path, self._result()) is False
        assert not memory.project_query_events_file(project_path).exists()

    def test_log_query_event_includes_session_id(self, monkeypatch, tmp_path):
        from neuralmind import memory
        from neuralmind.context_selector import ContextResult, TokenBudget

        project_path = tmp_path / "project"
        project_path.mkdir()
        monkeypatch.setenv("HOME", str(tmp_path))
        monkeypatch.setenv("USERPROFILE", str(tmp_path))
        monkeypatch.setenv("CLAUDE_SESSION_ID", "session-q")
        memory.write_consent_sentinel(True)

        result = ContextResult(
            context="c",
            budget=TokenBudget(l0_identity=10),
            layers_used=["L0", "L1", "L2", "L3"],
            communities_loaded=[1],
            search_hits=2,
            reduction_ratio=4.0,
        )
        memory.log_query_event(project_path, "q", result)

        payload = json.loads(
            memory.project_query_events_file(project_path)
            .read_text(encoding="utf-8")
            .strip()
            .splitlines()[0]
        )
        assert payload["session_id"] == "session-q"


class TestMemoryAggregations:
    """Tests for the aggregation helpers used by the selector tuner."""

    def _q(self, session_id, layers, communities, ts="2026-05-07T00:00:00+00:00"):
        return {
            "event_type": "query",
            "timestamp": ts,
            "session_id": session_id,
            "retrieval_summary": {
                "layers_used": layers,
                "communities_loaded": communities,
            },
        }

    def _w(self, session_id, ts="2026-05-07T00:00:00+00:00"):
        return {
            "event_type": "wakeup",
            "timestamp": ts,
            "session_id": session_id,
            "retrieval_summary": {"layers_used": ["L0", "L1"]},
        }

    def test_recent_events_filters_by_since_and_last_n(self):
        from neuralmind import memory

        events = [
            self._q("s", ["L0"], [], ts="2026-05-01T00:00:00+00:00"),
            self._q("s", ["L0"], [], ts="2026-05-05T00:00:00+00:00"),
            self._q("s", ["L0"], [], ts="2026-05-07T00:00:00+00:00"),
        ]
        windowed = memory.recent_events(events, since_ts="2026-05-04T00:00:00+00:00")
        assert len(windowed) == 2
        last = memory.recent_events(events, last_n=1)
        assert last[0]["timestamp"] == "2026-05-07T00:00:00+00:00"

    def test_escalation_rate_only_counts_queries_with_l3(self):
        from neuralmind import memory

        events = [
            self._q("s", ["L0:Identity", "L1:Summary", "L2:OnDemand(3 clusters)"], [1]),
            self._q(
                "s",
                ["L0:Identity", "L1:Summary", "L2:OnDemand(3 clusters)", "L3:Search(4 results)"],
                [1],
            ),
            self._q(
                "s",
                ["L0:Identity", "L1:Summary", "L2:OnDemand(2 clusters)", "L3:Search(4 results)"],
                [2],
            ),
            self._w("s"),  # wakeups don't count
        ]
        assert abs(memory.escalation_rate(events) - 2 / 3) < 1e-9

    def test_escalation_rate_matches_decorated_layer_strings(self):
        """layers_used elements are decorated by the selector — escalation_rate
        must match the 'L3:Search(...)' prefix, not a bare 'L3' element."""
        from neuralmind import memory

        escalated = [
            self._q(
                "s",
                ["L0:Identity", "L1:Summary", "L3:Search(4 results)"],
                [1],
            )
        ]
        not_escalated = [
            self._q("s", ["L0:Identity", "L1:Summary", "L2:OnDemand(3 clusters)"], [1])
        ]
        assert memory.escalation_rate(escalated) == 1.0
        assert memory.escalation_rate(not_escalated) == 0.0

    def test_escalation_rate_zero_on_empty(self):
        from neuralmind import memory

        assert memory.escalation_rate([]) == 0.0
        assert memory.escalation_rate([self._w("s")]) == 0.0

    def test_escalation_rate_does_not_match_l3_prefix_collision(self):
        """The predicate must match the L3 layer exactly ("L3" or
        "L3:..."), not any string that merely starts with "L3"."""
        from neuralmind import memory

        events = [self._q("s", ["L0:Identity", "L30:Hypothetical"], [1])]
        assert memory.escalation_rate(events) == 0.0

    def test_re_query_rate_counts_high_overlap_consecutive_queries(self):
        from neuralmind import memory

        events = [
            self._q("a", ["L0", "L1", "L2"], [1, 2]),
            self._q("a", ["L0", "L1", "L2"], [1, 2, 3]),  # 2/2 overlap → re-query
            self._q("a", ["L0", "L1", "L2"], [9]),  # no overlap
            self._q("b", ["L0", "L1", "L2"], [4]),
            self._q("b", ["L0", "L1", "L2"], [4]),  # full overlap → re-query
        ]
        # Pairs: (a:0,a:1) re-query, (a:1,a:2) not, (b:0,b:1) re-query → 2/3
        assert abs(memory.re_query_rate(events) - 2 / 3) < 1e-9

    def test_re_query_rate_isolates_sessions(self):
        from neuralmind import memory

        events = [
            self._q("a", ["L0"], [1]),
            self._q("b", ["L0"], [1]),  # different session, not a pair
        ]
        assert memory.re_query_rate(events) == 0.0

    def test_re_query_rate_excludes_empty_community_pairs(self):
        """A pair where either query loaded no communities carries no
        overlap signal — it must not count toward the denominator."""
        from neuralmind import memory

        events = [
            self._q("a", ["L0", "L1", "L2"], []),  # no communities
            self._q("a", ["L0", "L1", "L2"], [1, 2]),  # denom == 0 for this pair
            self._q("a", ["L0", "L1", "L2"], [1, 2]),  # real pair, full overlap
        ]
        # Only the (a:1, a:2) pair carries signal → 1/1, not 1/2.
        assert memory.re_query_rate(events) == 1.0

    def test_re_query_rate_skips_events_without_session_id(self):
        """Events with no session_id (pre-D1 logs) can't be ordered into
        sessions and must be skipped, not lumped under one shared key."""
        from neuralmind import memory

        events = [
            {
                "event_type": "query",
                "timestamp": "2026-05-07T00:00:00+00:00",
                "retrieval_summary": {"communities_loaded": [1, 2]},
            },
            {
                "event_type": "query",
                "timestamp": "2026-05-07T00:01:00+00:00",
                "retrieval_summary": {"communities_loaded": [1, 2]},
            },
        ]
        # Without session_id these are not a valid consecutive pair.
        assert memory.re_query_rate(events) == 0.0

    def test_wakeup_only_rate(self):
        from neuralmind import memory

        events = [
            self._w("s1"),  # wakeup-only session
            self._w("s2"),
            self._q("s2", ["L0", "L1"], [1]),  # s2 had a query, not wakeup-only
            self._q("s3", ["L0"], [1]),  # no wakeup → ineligible
        ]
        # Eligible (wakeup>=1): s1, s2. Wakeup-only: s1. → 1/2
        assert abs(memory.wakeup_only_rate(events) - 0.5) < 1e-9

    def test_wakeup_only_rate_zero_when_no_wakeups(self):
        from neuralmind import memory

        events = [self._q("s", ["L0"], [1])]
        assert memory.wakeup_only_rate(events) == 0.0


class TestMemoryPatternLearning:
    """Tests for cooccurrence pattern learning."""

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

    def test_extract_module_ids_from_event(self):
        """extract_module_ids_from_event extracts communities."""
        from neuralmind import memory

        event = {
            "event_type": "query",
            "retrieval_summary": {"communities_loaded": [0, 1, 2]},
        }
        modules = memory.extract_module_ids_from_event(event)
        assert modules == ["community_0", "community_1", "community_2"]

    def test_extract_module_ids_empty_event(self):
        """extract_module_ids handles events with no communities."""
        from neuralmind import memory

        event = {"event_type": "query", "retrieval_summary": {}}
        modules = memory.extract_module_ids_from_event(event)
        assert modules == []

    def test_build_cooccurrence_index(self):
        """build_cooccurrence_index analyzes events for patterns."""
        from neuralmind import memory

        events = [
            {
                "event_type": "query",
                "retrieval_summary": {"communities_loaded": [0, 1]},
            },
            {
                "event_type": "query",
                "retrieval_summary": {"communities_loaded": [0, 1]},
            },
            {
                "event_type": "query",
                "retrieval_summary": {"communities_loaded": [1, 2]},
            },
        ]

        index = memory.build_cooccurrence_index(events)

        assert index["metadata"]["version"] == "1"
        assert index["metadata"]["events_analyzed"] == 3
        assert index["cooccurrence"]["community_0|community_1"] == 2
        assert index["cooccurrence"]["community_1|community_2"] == 1
        assert index["module_frequency"]["community_0"] == 2
        assert index["module_frequency"]["community_1"] == 3

    def test_build_cooccurrence_index_empty(self):
        """build_cooccurrence_index handles empty events."""
        from neuralmind import memory

        index = memory.build_cooccurrence_index([])
        assert index["metadata"]["events_analyzed"] == 0
        assert index["metadata"]["patterns_learned"] == 0
        assert index["cooccurrence"] == {}

    def test_write_learned_patterns(self, tmp_path):
        """write_learned_patterns saves patterns to JSON file."""
        from neuralmind import memory

        project_path = tmp_path / "project"
        project_path.mkdir()

        index = {
            "metadata": {
                "version": "1",
                "created_at": "2026-04-20T00:00:00Z",
                "events_analyzed": 3,
                "patterns_learned": 2,
            },
            "cooccurrence": {"community_0|community_1": 2},
            "module_frequency": {"community_0": 2, "community_1": 3},
        }

        patterns_file = memory.write_learned_patterns(project_path, index)

        assert patterns_file.exists()
        assert patterns_file.name == "learned_patterns.json"
        assert ".neuralmind" in str(patterns_file)

        # Verify content
        saved_index = json.loads(patterns_file.read_text(encoding="utf-8"))
        assert saved_index["metadata"]["patterns_learned"] == 2
        assert saved_index["cooccurrence"]["community_0|community_1"] == 2
