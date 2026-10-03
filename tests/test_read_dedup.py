"""Read dedup — the compress-read hook replaces a repeat read with a stub.

stdlib-only (SQLite), like the rest of the synapse-layer tests.

The payloads use Claude Code's Read shape: the text sits under
``tool_response.file.content`` and a replacement goes back through
``hookSpecificOutput.updatedToolOutput`` (additionalContext would be added
next to the result instead of replacing it).
"""

from __future__ import annotations

import io
import json
import sys
from pathlib import Path

import pytest

from neuralmind.hooks import run_hook
from neuralmind.read_dedup import (
    MAX_AGE_SECS,
    MAX_ROWS,
    MIN_CHARS,
    PRUNE_AGE_SECS,
    ReadCache,
    find_read_text,
    read_cache_path,
    read_view,
    replace_read_text,
)

TEXT = "def handler(request):\n    return authenticate(request)\n" * 80  # ~4,400 chars


@pytest.fixture
def project(tmp_path, monkeypatch) -> Path:
    """A project NeuralMind already uses (has .neuralmind/), hooks isolated."""
    (tmp_path / ".neuralmind").mkdir()
    (tmp_path / "app.py").write_text(TEXT)
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.setenv("USERPROFILE", str(tmp_path / "home"))
    monkeypatch.setenv("NEURALMIND_SYNAPSE_EXPORT", "0")
    monkeypatch.setenv("NEURALMIND_TEAM_MEMORY", "0")
    for var in ("NEURALMIND_READ_DEDUP", "NEURALMIND_NO_LEARN", "NEURALMIND_BYPASS"):
        monkeypatch.delenv(var, raising=False)
    return tmp_path


def _run(action: str, payload: dict, monkeypatch) -> tuple[int, str]:
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps(payload)))
    captured = io.StringIO()
    monkeypatch.setattr(sys, "stdout", captured)
    return run_hook(action), captured.getvalue()


def _read_payload(project: Path, text: str = TEXT, **extra) -> dict:
    path = str(project / "app.py")
    payload = {
        "session_id": "session-a",
        "cwd": str(project),
        "hook_event_name": "PostToolUse",
        "tool_name": "Read",
        "tool_input": {"file_path": path},
        "tool_response": {
            "type": "text",
            "file": {
                "filePath": path,
                "content": text,
                "numLines": text.count("\n"),
                "startLine": 1,
                "totalLines": text.count("\n"),
            },
        },
    }
    payload.update(extra)
    return payload


def _read(project: Path, monkeypatch, **extra) -> dict | None:
    """Run the Read hook; return the updatedToolOutput it emitted, if any."""
    rc, out = _run("compress-read", _read_payload(project, **extra), monkeypatch)
    assert rc == 0
    if not out:
        return None
    return json.loads(out)["hookSpecificOutput"]["updatedToolOutput"]


class TestRepeatReads:
    def test_first_read_passes_through(self, project, monkeypatch):
        assert _read(project, monkeypatch) is None

    def test_repeat_read_is_replaced_with_a_stub(self, project, monkeypatch):
        _read(project, monkeypatch)
        updated = _read(project, monkeypatch)
        assert updated is not None
        # Same shape as Claude Code's own Read output — only the text changed.
        assert updated["type"] == "text"
        assert updated["file"]["filePath"] == str(project / "app.py")
        assert updated["file"]["startLine"] == 1
        stub = updated["file"]["content"]
        assert stub.startswith("[neuralmind read-dedup] app.py is unchanged")
        assert "read the file again" in stub
        assert len(stub) < len(TEXT) // 4
        assert updated["file"]["numLines"] == stub.count("\n") + 1

    def test_response_uses_updated_tool_output_not_additional_context(self, project, monkeypatch):
        _read(project, monkeypatch)
        _, out = _run("compress-read", _read_payload(project), monkeypatch)
        hso = json.loads(out)["hookSpecificOutput"]
        assert hso["hookEventName"] == "PostToolUse"
        assert "additionalContext" not in hso

    def test_read_after_a_stub_always_goes_through(self, project, monkeypatch):
        # Liveness: an agent whose earlier copy left its context gets the
        # file back by reading again — stubs never come twice in a row.
        assert _read(project, monkeypatch) is None
        assert _read(project, monkeypatch) is not None
        assert _read(project, monkeypatch) is None
        assert _read(project, monkeypatch) is not None

    def test_changed_content_is_not_deduped(self, project, monkeypatch):
        _read(project, monkeypatch)
        changed = TEXT + "def extra():\n    pass\n"
        assert (
            _read(
                project, monkeypatch, tool_response=_read_payload(project, changed)["tool_response"]
            )
            is None
        )

    def test_another_range_of_the_file_is_a_different_read(self, project, monkeypatch):
        _read(project, monkeypatch)
        ranged = {"file_path": str(project / "app.py"), "offset": 40, "limit": 20}
        assert _read(project, monkeypatch, tool_input=ranged) is None
        # ...but repeating that same range is a repeat.
        assert _read(project, monkeypatch, tool_input=ranged) is not None

    def test_sessions_do_not_share_reads(self, project, monkeypatch):
        _read(project, monkeypatch, session_id="session-a")
        assert _read(project, monkeypatch, session_id="session-b") is None

    def test_subagent_and_main_agent_do_not_share_reads(self, project, monkeypatch):
        # A subagent's context never held the main agent's read (and vice versa).
        _read(project, monkeypatch)
        assert _read(project, monkeypatch, agent_id="a4d2c8f1") is None
        assert _read(project, monkeypatch, agent_id="a4d2c8f1") is not None

    def test_small_reads_are_never_stubbed(self, project, monkeypatch):
        small = "x = 1\n" * 10
        assert len(small) < MIN_CHARS
        response = _read_payload(project, small)["tool_response"]
        _read(project, monkeypatch, tool_response=response)
        assert _read(project, monkeypatch, tool_response=response) is None

    def test_legacy_flat_shape_is_replaced_in_place(self, project, monkeypatch):
        flat = {"content": TEXT}
        _read(project, monkeypatch, tool_response=flat)
        updated = _read(project, monkeypatch, tool_response=flat)
        assert set(updated) == {"content"}
        assert updated["content"].startswith("[neuralmind read-dedup]")

    def test_non_text_reads_are_left_alone(self, project, monkeypatch):
        image = {"type": "image", "file": {"base64": "iVBORw0K" * 500, "type": "image/png"}}
        _read(project, monkeypatch, tool_response=image)
        assert _read(project, monkeypatch, tool_response=image) is None


class TestGates:
    def test_no_session_id_means_no_dedup(self, project, monkeypatch):
        payload = _read_payload(project)
        del payload["session_id"]
        for _ in range(2):
            rc, out = _run("compress-read", payload, monkeypatch)
            assert (rc, out) == (0, "")
        assert not read_cache_path(project).exists()

    def test_opt_out(self, project, monkeypatch):
        monkeypatch.setenv("NEURALMIND_READ_DEDUP", "0")
        _read(project, monkeypatch)
        assert _read(project, monkeypatch) is None
        assert not read_cache_path(project).exists()

    def test_no_learn_writes_nothing(self, project, monkeypatch):
        monkeypatch.setenv("NEURALMIND_NO_LEARN", "1")
        _read(project, monkeypatch)
        assert _read(project, monkeypatch) is None
        assert not read_cache_path(project).exists()

    def test_bypass(self, project, monkeypatch):
        monkeypatch.setenv("NEURALMIND_BYPASS", "1")
        _read(project, monkeypatch)
        assert _read(project, monkeypatch) is None

    def test_project_without_neuralmind_dir_is_untouched(self, tmp_path, monkeypatch):
        # A globally installed hook must not create .neuralmind/ in every repo.
        (tmp_path / "app.py").write_text(TEXT)
        for _ in range(2):
            assert _read(tmp_path, monkeypatch) is None
        assert not (tmp_path / ".neuralmind").exists()

    def test_corrupt_cache_fails_open(self, project, monkeypatch):
        read_cache_path(project).write_bytes(b"this is not a sqlite database" * 100)
        for _ in range(2):
            assert _read(project, monkeypatch) is None


class TestContextResets:
    def test_session_start_forgets_the_session(self, project, monkeypatch):
        _read(project, monkeypatch)
        rc, _ = _run(
            "session-start",
            {"session_id": "session-a", "cwd": str(project), "source": "compact"},
            monkeypatch,
        )
        assert rc == 0
        assert _read(project, monkeypatch) is None

    def test_pre_compact_forgets_the_session(self, project, monkeypatch):
        _read(project, monkeypatch)
        rc, _ = _run("pre-compact", {"session_id": "session-a", "cwd": str(project)}, monkeypatch)
        assert rc == 0
        assert _read(project, monkeypatch) is None

    def test_reset_leaves_other_sessions_alone(self, project, monkeypatch):
        _read(project, monkeypatch, session_id="session-b")
        _run("pre-compact", {"session_id": "session-a", "cwd": str(project)}, monkeypatch)
        assert _read(project, monkeypatch, session_id="session-b") is not None

    def test_reset_does_not_create_the_cache(self, project, monkeypatch):
        _run("pre-compact", {"session_id": "session-a", "cwd": str(project)}, monkeypatch)
        assert not read_cache_path(project).exists()


class TestReadCache:
    def test_old_delivery_does_not_count(self, tmp_path):
        cache = ReadCache(tmp_path)
        assert cache.observe("s", "", "/f.py", "", "h", now=1000.0) is None
        late = 1000.0 + MAX_AGE_SECS + 1
        assert cache.observe("s", "", "/f.py", "", "h", now=late) is None
        # The late read re-armed the entry as a fresh delivery.
        repeat = cache.observe("s", "", "/f.py", "", "h", now=late + 5)
        assert repeat is not None and repeat.delivered_at == late

    def test_repeat_reports_reads_and_delivery_time(self, tmp_path):
        cache = ReadCache(tmp_path)
        cache.observe("s", "", "/f.py", "", "h", now=100.0)
        repeat = cache.observe("s", "", "/f.py", "", "h", now=160.0)
        assert repeat.reads == 2
        assert repeat.delivered_at == 100.0

    def test_prune_drops_old_rows_and_caps_the_table(self, tmp_path, monkeypatch):
        import neuralmind.read_dedup as read_dedup

        assert MAX_ROWS >= 1000  # the real cap; patched down to keep this test fast
        monkeypatch.setattr(read_dedup, "MAX_ROWS", 10)
        cache = ReadCache(tmp_path)
        cache.observe("old", "", "/f.py", "", "h", now=0.0)
        now = PRUNE_AGE_SECS + 10.0
        for i in range(15):
            cache.observe("s", "", f"/f{i}.py", "", "h", now=now + i)
        removed = cache.prune(now=now + 20)
        assert removed == 6  # the stale session row + 5 over the cap
        assert cache.stats()["rows"] == 10
        # The newest rows survive the cap.
        assert cache.observe("s", "", "/f14.py", "", "h", now=now + 21) is not None
        assert cache.observe("s", "", "/f0.py", "", "h", now=now + 21) is None

    def test_clear_session_covers_every_agent(self, tmp_path):
        cache = ReadCache(tmp_path)
        cache.observe("s", "", "/f.py", "", "h", now=1.0)
        cache.observe("s", "agent-1", "/f.py", "", "h", now=1.0)
        cache.observe("t", "", "/f.py", "", "h", now=1.0)
        assert cache.clear_session("s") == 2
        assert cache.stats()["sessions"] == 1


class TestHelpers:
    def test_read_view(self):
        assert read_view({"file_path": "/a.py"}) == ""
        assert read_view({"file_path": "/a.py", "offset": 10, "limit": 5}) != ""
        assert read_view({"offset": 10}) != read_view({"offset": 11})

    def test_find_read_text(self):
        assert find_read_text({"type": "text", "file": {"content": "abc"}}) == "abc"
        assert find_read_text({"content": "abc"}) == "abc"
        assert find_read_text({"type": "notebook", "file": {"cells": []}}) is None
        assert find_read_text("plain string") is None
        assert find_read_text(None) is None

    def test_replace_read_text_does_not_mutate_the_original(self):
        original = {"type": "text", "file": {"content": "abc", "numLines": 1}}
        updated = replace_read_text(original, "stub\nline")
        assert original["file"]["content"] == "abc"
        assert updated["file"] == {"content": "stub\nline", "numLines": 2}
