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
        # Our three matchers should be present
        post_tool = settings["hooks"]["PostToolUse"]
        matchers = {block["matcher"] for block in post_tool}
        assert matchers == {"Read", "Bash", "Grep"}

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
        # User's hook still there
        edit_hook = [b for b in updated["hooks"]["PostToolUse"] if b["matcher"] == "Edit"]
        assert len(edit_hook) == 1
        assert edit_hook[0]["hooks"][0]["command"] == "prettier --write"
        # Other top-level settings preserved
        assert updated.get("someOtherSetting") == "keep-me"
        # Neuralmind matchers added
        matchers = {b["matcher"] for b in updated["hooks"]["PostToolUse"]}
        assert "Read" in matchers and "Bash" in matchers and "Grep" in matchers

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
