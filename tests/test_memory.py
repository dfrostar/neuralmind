"""Tests for local-first implicit continual-learning scaffolding."""

from __future__ import annotations

import io
import json
from types import SimpleNamespace
from unittest.mock import MagicMock


class _TTYStringIO(io.StringIO):
    def isatty(self) -> bool:
        return True


def _raise_no_prompt(_: str) -> str:
    raise RuntimeError("no prompt")


def _read_last_jsonl_entry(path) -> dict:
    return json.loads(path.read_text(encoding="utf-8").strip().splitlines()[-1])


class TestConsent:
    def test_non_interactive_defaults_to_disabled(self, tmp_path, monkeypatch):
        monkeypatch.setenv("NEURALMIND_HOME", str(tmp_path / "global"))
        monkeypatch.delenv("NEURALMIND_IMPLICIT_LEARNING_OPT_IN", raising=False)

        from neuralmind.memory import consent_sentinel_path, ensure_implicit_learning_consent

        assert ensure_implicit_learning_consent() is False
        assert not consent_sentinel_path().exists()

    def test_prompt_accepts_once_and_persists(self, tmp_path, monkeypatch):
        monkeypatch.setenv("NEURALMIND_HOME", str(tmp_path / "global"))
        monkeypatch.delenv("NEURALMIND_IMPLICIT_LEARNING_OPT_IN", raising=False)

        stdin = _TTYStringIO()
        stdout = _TTYStringIO()
        monkeypatch.setattr("sys.stdin", stdin)
        monkeypatch.setattr("sys.stdout", stdout)
        monkeypatch.setattr("builtins.input", lambda _: "y")

        from neuralmind.memory import consent_sentinel_path, ensure_implicit_learning_consent

        assert ensure_implicit_learning_consent() is True
        payload = json.loads(consent_sentinel_path().read_text(encoding="utf-8"))
        assert payload["opted_in"] is True
        assert payload["source"] == "prompt"

        monkeypatch.setattr("builtins.input", _raise_no_prompt)
        assert ensure_implicit_learning_consent() is True


class TestImplicitMemoryLogging:
    def test_logs_to_global_and_project_when_opted_in(self, tmp_path, monkeypatch):
        monkeypatch.setenv("NEURALMIND_HOME", str(tmp_path / "global"))
        monkeypatch.setenv("NEURALMIND_IMPLICIT_LEARNING_OPT_IN", "true")

        project_path = tmp_path / "project"
        project_path.mkdir(parents=True)

        from neuralmind.memory import log_implicit_learning_event

        assert (
            log_implicit_learning_event(
                project_path=project_path,
                event="query",
                details={"question": "how auth works"},
            )
            is True
        )

        global_log = tmp_path / "global" / "memory" / "implicit_learning.jsonl"
        project_log = project_path / ".neuralmind" / "memory" / "implicit_learning.jsonl"

        assert global_log.exists()
        assert project_log.exists()
        global_event = _read_last_jsonl_entry(global_log)
        project_event = _read_last_jsonl_entry(project_log)
        assert global_event["event"] == "query"
        assert project_event["details"]["question"] == "how auth works"

    def test_does_not_log_when_opted_out(self, tmp_path, monkeypatch):
        monkeypatch.setenv("NEURALMIND_HOME", str(tmp_path / "global"))
        monkeypatch.setenv("NEURALMIND_IMPLICIT_LEARNING_OPT_IN", "no")

        project_path = tmp_path / "project"
        project_path.mkdir(parents=True)

        from neuralmind.memory import log_implicit_learning_event

        assert log_implicit_learning_event(project_path=project_path, event="query") is False
        assert not (tmp_path / "global" / "memory" / "implicit_learning.jsonl").exists()
        assert not (project_path / ".neuralmind" / "memory" / "implicit_learning.jsonl").exists()


class TestCoreIntegration:
    def test_query_and_wakeup_log_interactions(self, tmp_path, monkeypatch):
        from neuralmind.core import NeuralMind

        fake_result = SimpleNamespace(
            budget=SimpleNamespace(total=42),
            layers_used=["L0", "L1"],
            communities_loaded=[1],
            search_hits=2,
        )
        mind = NeuralMind(str(tmp_path))
        mind._built = True
        mind.selector = SimpleNamespace(
            get_wakeup_context=lambda: fake_result,
            get_query_context=lambda question: fake_result,
        )

        log_mock = MagicMock()
        monkeypatch.setattr(mind, "_log_interaction", log_mock)

        mind.wakeup()
        mind.query("auth question")

        assert log_mock.call_count == 2
        assert log_mock.call_args_list[0].args[0] == "wakeup"
        assert log_mock.call_args_list[1].args[0] == "query"

    def test_search_logs_interaction(self, tmp_path, monkeypatch):
        from neuralmind.core import NeuralMind

        mind = NeuralMind(str(tmp_path))
        mind._built = True
        mind.selector = SimpleNamespace()
        monkeypatch.setattr(mind.embedder, "search", lambda query, n, **kwargs: [{"id": "node"}])

        log_mock = MagicMock()
        monkeypatch.setattr(mind, "_log_interaction", log_mock)

        result = mind.search("auth", n=3, file_type="code")

        assert len(result) == 1
        log_mock.assert_called_once()
        assert log_mock.call_args.args[0] == "search"
