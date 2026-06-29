"""Tests for neuralmind.hooks — Claude Code PostToolUse integration."""

from __future__ import annotations

import io
import json
import sys
from pathlib import Path

from neuralmind.hooks import (
    _is_neuralmind_block,
    install_hooks,
    run_hook,
)


class TestInstallProject:
    def test_install_fresh(self, tmp_path):
        """Install into a project with no existing .claude/settings.json."""
        result = install_hooks(scope="project", project_path=str(tmp_path))
        assert result["action"] == "installed"

        settings_path = tmp_path / ".claude" / "settings.json"
        assert settings_path.exists()
        settings = json.loads(settings_path.read_text())
        # Compressor matchers + reuse-feedback Edit/Write matchers (v0.38.0)
        post_tool = settings["hooks"]["PostToolUse"]
        matchers = {block["matcher"] for block in post_tool}
        assert matchers == {"Read", "Bash", "Grep", "Edit", "Write"}

    def test_install_preserves_user_hooks(self, tmp_path):
        """Installing should not clobber user's existing hooks."""
        settings_path = tmp_path / ".claude" / "settings.json"
        settings_path.parent.mkdir(parents=True, exist_ok=True)
        # User's existing custom hook
        user_settings = {
            "hooks": {
                "PostToolUse": [
                    {
                        "matcher": "Edit",
                        "hooks": [{"type": "command", "command": "prettier --write"}],
                    }
                ]
            },
            "someOtherSetting": "keep-me",
        }
        settings_path.write_text(json.dumps(user_settings, indent=2))

        install_hooks(scope="project", project_path=str(tmp_path))

        updated = json.loads(settings_path.read_text())
        # User's Edit hook still there. NeuralMind now also registers an Edit
        # matcher (reuse feedback), so identify the user's block by its command.
        edit_hooks = [b for b in updated["hooks"]["PostToolUse"] if b["matcher"] == "Edit"]
        user_edit = [b for b in edit_hooks if b["hooks"][0]["command"] == "prettier --write"]
        assert len(user_edit) == 1
        # Other top-level settings preserved
        assert updated.get("someOtherSetting") == "keep-me"
        # Neuralmind matchers added
        matchers = {b["matcher"] for b in updated["hooks"]["PostToolUse"]}
        assert {"Read", "Bash", "Grep", "Edit", "Write"} <= matchers

    def test_install_idempotent(self, tmp_path):
        """Running install twice shouldn't duplicate hooks."""
        install_hooks(scope="project", project_path=str(tmp_path))
        install_hooks(scope="project", project_path=str(tmp_path))

        settings = json.loads((tmp_path / ".claude" / "settings.json").read_text())
        matchers = [b["matcher"] for b in settings["hooks"]["PostToolUse"]]
        # Each matcher should appear exactly once
        assert matchers.count("Read") == 1
        assert matchers.count("Bash") == 1
        assert matchers.count("Grep") == 1
        assert matchers.count("Edit") == 1
        assert matchers.count("Write") == 1

    def test_uninstall_removes_only_ours(self, tmp_path):
        """Uninstall should leave user's hooks untouched."""
        settings_path = tmp_path / ".claude" / "settings.json"
        settings_path.parent.mkdir(parents=True, exist_ok=True)
        user_settings = {
            "hooks": {
                "PostToolUse": [
                    {
                        "matcher": "Edit",
                        "hooks": [{"type": "command", "command": "prettier"}],
                    }
                ]
            }
        }
        settings_path.write_text(json.dumps(user_settings))

        install_hooks(scope="project", project_path=str(tmp_path))
        result = install_hooks(scope="project", project_path=str(tmp_path), uninstall=True)
        assert result["action"] == "uninstalled"

        final = json.loads(settings_path.read_text())
        matchers = [b["matcher"] for b in final["hooks"]["PostToolUse"]]
        assert matchers == ["Edit"]  # Only user's hook remains

    def test_uninstall_removes_empty_file(self, tmp_path):
        """Uninstalling all hooks from a neuralmind-only settings file removes it."""
        install_hooks(scope="project", project_path=str(tmp_path))
        result = install_hooks(scope="project", project_path=str(tmp_path), uninstall=True)
        assert result.get("removed_file") is True
        assert not (tmp_path / ".claude" / "settings.json").exists()


class TestInstallGlobal:
    def test_global_scope(self, tmp_path, monkeypatch):
        """--global writes to ~/.claude/settings.json (Path.home() mocked)."""
        monkeypatch.setenv("HOME", str(tmp_path))
        monkeypatch.setenv("USERPROFILE", str(tmp_path))  # Windows
        # Path.home() uses HOME (POSIX) or USERPROFILE (Windows)

        install_hooks(scope="global")

        global_settings = Path(str(tmp_path)) / ".claude" / "settings.json"
        assert global_settings.exists()


class TestIsNeuralmindBlock:
    def test_identifies_our_block(self):
        block = {
            "matcher": "Read",
            "hooks": [{"type": "command", "command": "neuralmind _hook compress-read"}],
        }
        assert _is_neuralmind_block(block) is True

    def test_rejects_other_block(self):
        block = {
            "matcher": "Edit",
            "hooks": [{"type": "command", "command": "prettier"}],
        }
        assert _is_neuralmind_block(block) is False

    def test_handles_bad_input(self):
        assert _is_neuralmind_block(None) is False
        assert _is_neuralmind_block({}) is False
        assert _is_neuralmind_block({"hooks": []}) is False


class TestRunHook:
    """Test the runtime hook entrypoint with mocked stdin/stdout."""

    def _invoke(self, action: str, payload: dict, monkeypatch):
        """Helper: feed payload to run_hook, capture stdout."""
        monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps(payload)))
        captured = io.StringIO()
        monkeypatch.setattr(sys, "stdout", captured)
        exit_code = run_hook(action)
        return exit_code, captured.getvalue()

    def test_compress_bash_emits(self, monkeypatch):
        # Use a verbose-line payload that exceeds BASH_MAX_CHARS (3000 default)
        verbose_line = "tests/test_module.py::test_function_with_descriptive_name PASSED"
        payload = {
            "tool_name": "Bash",
            "tool_input": {"command": "pytest -v"},
            "tool_response": {
                "stdout": "\n".join([verbose_line] * 100) + "\n===== 100 passed in 3.21s =====",
                "stderr": "",
                "exit_code": 0,
            },
        }
        exit_code, output = self._invoke("compress-bash", payload, monkeypatch)
        assert exit_code == 0
        # Should have emitted a JSON response (stdout non-empty)
        assert output.strip()
        # Decode and verify structure
        resp = json.loads(output)
        assert "hookSpecificOutput" in resp
        ctx = resp["hookSpecificOutput"]["additionalContext"]
        assert "[neuralmind:" in ctx
        assert "100 passed" in ctx  # Summary preserved

    def test_cap_search_emits(self, monkeypatch):
        payload = {
            "tool_name": "Grep",
            "tool_input": {"pattern": "foo"},
            "tool_response": {
                "content": "\n".join(f"match_{i}" for i in range(100)),
            },
        }
        exit_code, output = self._invoke("cap-search", payload, monkeypatch)
        assert exit_code == 0
        resp = json.loads(output)
        assert "capped at 25" in resp["hookSpecificOutput"]["additionalContext"]

    def test_empty_input_noops(self, monkeypatch):
        """Empty stdin should fail-open silently."""
        monkeypatch.setattr(sys, "stdin", io.StringIO(""))
        monkeypatch.setattr(sys, "stdout", io.StringIO())
        assert run_hook("compress-bash") == 0

    def test_invalid_json_noops(self, monkeypatch):
        monkeypatch.setattr(sys, "stdin", io.StringIO("not json"))
        captured = io.StringIO()
        monkeypatch.setattr(sys, "stdout", captured)
        assert run_hook("compress-bash") == 0
        assert captured.getvalue() == ""

    def test_bypass_env(self, monkeypatch):
        monkeypatch.setenv("NEURALMIND_BYPASS", "1")
        payload = {
            "tool_name": "Bash",
            "tool_response": {"stdout": "x" * 10000, "exit_code": 1},
        }
        exit_code, output = self._invoke("compress-bash", payload, monkeypatch)
        # With bypass set, no transformation
        assert output == ""
        assert exit_code == 0

    def test_unknown_action_noops(self, monkeypatch):
        monkeypatch.setattr(sys, "stdin", io.StringIO("{}"))
        captured = io.StringIO()
        monkeypatch.setattr(sys, "stdout", captured)
        assert run_hook("nonsense-action") == 0

    def test_edit_activity_invokes_feedback(self, monkeypatch):
        """Edit/Write route to record_edit_activity and emit nothing."""
        import neuralmind.hooks as hooks_mod

        calls = []
        monkeypatch.setattr(
            hooks_mod,
            "_record_edit_activity",
            lambda cwd, fp, code: calls.append((cwd, fp, code)),
        )
        payload = {
            "tool_name": "Edit",
            "tool_input": {"file_path": "api/routes.py", "new_string": "authenticate_user()"},
            "tool_response": {},
            "cwd": "/proj",
        }
        exit_code, output = self._invoke("edit-activity", payload, monkeypatch)
        assert exit_code == 0
        assert output == ""  # pure side effect, emits nothing
        assert calls == [("/proj", "api/routes.py", "authenticate_user()")]

    def test_edit_activity_opt_out(self, monkeypatch):
        """NEURALMIND_REUSE_FEEDBACK=0 makes the branch a no-op."""
        import neuralmind.hooks as hooks_mod

        monkeypatch.setenv("NEURALMIND_REUSE_FEEDBACK", "0")
        calls = []
        monkeypatch.setattr(hooks_mod, "_record_edit_activity", lambda *a: calls.append(a))
        payload = {
            "tool_name": "Write",
            "tool_input": {"file_path": "x.py", "content": "def f(): pass"},
            "tool_response": {},
            "cwd": "/proj",
        }
        exit_code, output = self._invoke("edit-activity", payload, monkeypatch)
        assert exit_code == 0
        assert output == ""
        assert calls == []  # gated off — feedback never runs

    def test_compress_bash_populates_recovery_cache(self, monkeypatch, tmp_path):
        """The compress-bash hook stashes raw output to .neuralmind/last_output.json.

        This is what makes `neuralmind last` work — without the side-effect
        write, agents lose the dropped middle the moment the hook returns.
        """
        from neuralmind.output_cache import read_last_output

        verbose_line = "tests/test_module.py::test_function PASSED"
        payload = {
            "tool_name": "Bash",
            "tool_input": {"command": "pytest -v"},
            "tool_response": {
                "stdout": "\n".join([verbose_line] * 100) + "\n===== 100 passed =====",
                "stderr": "",
                "exit_code": 0,
            },
            "cwd": str(tmp_path),
        }
        self._invoke("compress-bash", payload, monkeypatch)
        cached = read_last_output(tmp_path)
        assert cached is not None
        # Raw output preserved verbatim — that's the whole point of the cache.
        assert cached["stdout"].count(verbose_line) == 100
        assert cached["command"] == "pytest -v"
        assert cached["exit_code"] == 0
