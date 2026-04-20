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
