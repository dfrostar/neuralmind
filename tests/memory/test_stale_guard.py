"""Tests for the PreToolUse stale-decision guard (v4.2.0).

The guard is the runtime counterpart of the eval harness's
stale_influence_rate metric: instead of measuring how often stale memory
steers edits, it surfaces stale decisions before the edit lands.
"""

import json
import os
import sys
from pathlib import Path
from unittest import mock

import pytest

from neuralmind.hooks import HOOK_VERSION, _hook_block, _stale_decision_context
from neuralmind.memory.store import DecisionStore


@pytest.fixture
def project(tmp_path: Path) -> Path:
    (tmp_path / ".neuralmind").mkdir(exist_ok=True)
    return tmp_path


@pytest.fixture
def store(project: Path) -> DecisionStore:
    return DecisionStore(project)


def _record(store: DecisionStore, title: str, files: list[str], status: str = "ACTIVE"):
    return store.record(
        title=title,
        rationale=f"Rationale for {title}",
        commit_sha="abc1234",
        files_affected=files,
        status=status,
    )


class TestStaleGuardContext:
    def test_stale_decision_surfaces(self, store, project):
        _record(store, "Use SQLite WAL", ["neuralmind/db.py"], status="STALE")
        ctx = _stale_decision_context(str(project), "neuralmind/db.py")
        assert "stale-guard" in ctx
        assert "Use SQLite WAL" in ctx
        assert "STALE" in ctx

    def test_active_decision_not_surfaced(self, store, project):
        _record(store, "Use SQLite WAL", ["neuralmind/db.py"], status="ACTIVE")
        assert _stale_decision_context(str(project), "neuralmind/db.py") == ""

    def test_invalidated_decision_surfaced(self, store, project):
        _record(store, "Old auth flow", ["neuralmind/auth.py"], status="INVALIDATED")
        ctx = _stale_decision_context(str(project), "neuralmind/auth.py")
        assert "Old auth flow" in ctx
        assert "INVALIDATED" in ctx

    def test_absolute_path_normalized(self, store, project):
        _record(store, "Use SQLite WAL", ["neuralmind/db.py"], status="STALE")
        abs_path = str(project / "neuralmind" / "db.py")
        ctx = _stale_decision_context(str(project), abs_path)
        assert "Use SQLite WAL" in ctx

    def test_unrelated_file_no_output(self, store, project):
        _record(store, "Use SQLite WAL", ["neuralmind/db.py"], status="STALE")
        assert _stale_decision_context(str(project), "other/file.py") == ""

    def test_no_store_fail_open(self, tmp_path):
        # Project with no .neuralmind/ dir — must return "" not raise.
        assert _stale_decision_context(str(tmp_path), "any/file.py") == ""

    def test_caps_at_five(self, store, project):
        for i in range(7):
            _record(store, f"Stale decision {i}", ["neuralmind/db.py"], status="STALE")
        ctx = _stale_decision_context(str(project), "neuralmind/db.py")
        # Header states the true count; at most 5 records are listed.
        assert "7 decision(s)" in ctx
        assert ctx.count("- [STALE]") == 5
        assert "2 more" in ctx


class TestStaleGuardHookRegistration:
    def test_hook_block_includes_pretooluse(self):
        block = _hook_block()
        assert "PreToolUse" in block
        matchers = [b.get("matcher") for b in block["PreToolUse"]]
        assert any("Edit" in m and "Write" in m for m in matchers)

    def test_hook_version_bumped(self):
        assert HOOK_VERSION == "3"


class TestStaleGuardRuntime:
    """End-to-end: run_hook('stale-guard') with a stdin payload."""

    def _run(self, project: Path, payload: dict, env: dict | None = None) -> str:
        from neuralmind.hooks import run_hook

        with mock.patch.object(sys, "stdin") as stdin:
            stdin.read.return_value = json.dumps(payload)
            with mock.patch.object(sys, "stdout") as stdout:
                stdout.write = mock.MagicMock()
                env_vars = {**os.environ, **(env or {})}
                with mock.patch.dict(os.environ, env_vars, clear=False):
                    run_hook("stale-guard")
                return stdout.write.call_args[0][0] if stdout.write.call_args else ""

    def test_stale_edit_emits_context(self, store, project):
        _record(store, "Use SQLite WAL", ["neuralmind/db.py"], status="STALE")
        payload = {
            "tool_name": "Edit",
            "tool_input": {"file_path": "neuralmind/db.py"},
            "cwd": str(project),
        }
        out = self._run(project, payload)
        assert "stale-guard" in out
        assert "Use SQLite WAL" in out

    def test_clean_edit_emits_nothing(self, store, project):
        _record(store, "Use SQLite WAL", ["neuralmind/db.py"], status="ACTIVE")
        payload = {
            "tool_name": "Edit",
            "tool_input": {"file_path": "neuralmind/db.py"},
            "cwd": str(project),
        }
        assert self._run(project, payload) == ""

    def test_env_optout(self, store, project):
        _record(store, "Use SQLite WAL", ["neuralmind/db.py"], status="STALE")
        payload = {
            "tool_name": "Edit",
            "tool_input": {"file_path": "neuralmind/db.py"},
            "cwd": str(project),
        }
        assert self._run(project, payload, env={"NEURALMIND_STALE_GUARD": "0"}) == ""
