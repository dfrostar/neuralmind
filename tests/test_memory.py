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
