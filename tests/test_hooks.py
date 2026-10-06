"""Tests for neuralmind.hooks — Claude Code PostToolUse integration."""

from __future__ import annotations

import io
import json
import os
import sys
from pathlib import Path

import pytest

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


class TestInstallRefusesUnparsableSettings:
    """A settings.json that isn't a JSON object is never rewritten or deleted.

    It used to be read as ``{}``: install then replaced the user's permissions,
    model and env with just our hooks, and --uninstall deleted the file. A
    single trailing comma was enough.
    """

    USER_SETTINGS = (
        "{\n"
        '  "model": "opus",\n'
        '  "permissions": {"allow": ["Bash(npm test)"]},\n'
        '  "env": {"FOO": "bar"},\n'
        "}\n"
    )

    def _write(self, tmp_path, text):
        settings_path = tmp_path / ".claude" / "settings.json"
        settings_path.parent.mkdir(parents=True, exist_ok=True)
        settings_path.write_text(text, encoding="utf-8")
        return settings_path

    def test_install_refuses_trailing_comma_file(self, tmp_path):
        settings_path = self._write(tmp_path, self.USER_SETTINGS)
        with pytest.raises(ValueError, match="not valid JSON"):
            install_hooks(scope="project", project_path=str(tmp_path))
        assert settings_path.read_text(encoding="utf-8") == self.USER_SETTINGS

    def test_uninstall_refuses_and_never_deletes(self, tmp_path):
        settings_path = self._write(tmp_path, self.USER_SETTINGS)
        with pytest.raises(ValueError, match="not valid JSON"):
            install_hooks(scope="project", project_path=str(tmp_path), uninstall=True)
        assert settings_path.read_text(encoding="utf-8") == self.USER_SETTINGS

    def test_refuses_non_object_top_level(self, tmp_path):
        settings_path = self._write(tmp_path, "[1, 2]")
        with pytest.raises(ValueError, match="JSON object"):
            install_hooks(scope="project", project_path=str(tmp_path))
        assert settings_path.read_text(encoding="utf-8") == "[1, 2]"

    def test_refuses_non_object_hooks_value(self, tmp_path):
        text = json.dumps({"model": "opus", "hooks": ["not", "a", "mapping"]})
        settings_path = self._write(tmp_path, text)
        with pytest.raises(ValueError, match="hooks"):
            install_hooks(scope="project", project_path=str(tmp_path))
        assert settings_path.read_text(encoding="utf-8") == text

    def test_empty_file_is_treated_as_no_settings(self, tmp_path):
        settings_path = self._write(tmp_path, "  \n")
        result = install_hooks(scope="project", project_path=str(tmp_path))
        assert result["action"] == "installed"
        assert "hooks" in json.loads(settings_path.read_text(encoding="utf-8"))

    def test_cli_reports_error_and_exits_nonzero(self, tmp_path, capsys):
        settings_path = self._write(tmp_path, self.USER_SETTINGS)
        from neuralmind.cli import build_parser, cmd_install_hooks

        args = build_parser().parse_args(["install-hooks", str(tmp_path)])
        with pytest.raises(SystemExit) as exc:
            cmd_install_hooks(args)
        assert exc.value.code == 1
        assert "not valid JSON" in capsys.readouterr().out
        assert settings_path.read_text(encoding="utf-8") == self.USER_SETTINGS


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

    # The tool-output actions inject nothing: Claude Code adds PostToolUse
    # additionalContext next to the tool result rather than replacing it, so a
    # compressed copy only added tokens (docs/benchmarks/compression.md).

    def test_compress_bash_injects_nothing(self, monkeypatch, tmp_path):
        # Over BASH_MAX_CHARS, where the hook used to append its compressed copy.
        verbose_line = "tests/test_module.py::test_function_with_descriptive_name PASSED"
        payload = {
            "tool_name": "Bash",
            "tool_input": {"command": "pytest -v"},
            "tool_response": {
                "stdout": "\n".join([verbose_line] * 100) + "\n===== 100 passed in 3.21s =====",
                "stderr": "",
                "interrupted": False,
                "isImage": False,
            },
            "cwd": str(tmp_path),
        }
        exit_code, output = self._invoke("compress-bash", payload, monkeypatch)
        assert exit_code == 0
        assert output == ""

    def test_small_bash_output_is_not_repeated(self, monkeypatch, tmp_path):
        # Under the threshold the "compressed" copy used to be the whole output
        # again, doubling what Claude saw.
        payload = {
            "tool_name": "Bash",
            "tool_input": {"command": "ls"},
            "tool_response": {"stdout": "README.md\nsetup.py\n", "stderr": ""},
            "cwd": str(tmp_path),
        }
        exit_code, output = self._invoke("compress-bash", payload, monkeypatch)
        assert exit_code == 0
        assert output == ""

    def test_cap_search_injects_nothing(self, monkeypatch):
        payload = {
            "tool_name": "Grep",
            "tool_input": {"pattern": "foo", "output_mode": "content"},
            "tool_response": {
                "mode": "content",
                "numFiles": 1,
                "filenames": ["a.py"],
                "content": "\n".join(f"a.py:{i}:match_{i}" for i in range(100)),
            },
        }
        exit_code, output = self._invoke("cap-search", payload, monkeypatch)
        assert exit_code == 0
        assert output == ""

    def test_offload_injects_nothing(self, monkeypatch):
        # The opt-in offload action used to point Claude at a temp file
        # holding any output over the offload threshold; it now returns
        # nothing, whichever key the output arrives under.
        big = "x" * 50_000
        for tool_response in ({"output": big}, {"content": big}):
            payload = {
                "tool_name": "Bash",
                "tool_input": {"command": "cat big.json"},
                "tool_response": tool_response,
            }
            exit_code, output = self._invoke("offload", payload, monkeypatch)
            assert exit_code == 0
            assert output == ""

    def test_compress_read_injects_nothing(self, monkeypatch, tmp_path):
        path = tmp_path / "module.py"
        text = "def f():\n    return 1\n" * 200
        path.write_text(text)
        for tool_response in (
            # Claude Code's shape: the text is under file.content.
            {
                "type": "text",
                "file": {
                    "filePath": str(path),
                    "content": text,
                    "numLines": 400,
                    "startLine": 1,
                    "totalLines": 400,
                },
            },
            # The older flat shape the hook was written against.
            {"content": text},
        ):
            payload = {
                "tool_name": "Read",
                "tool_input": {"file_path": str(path)},
                "tool_response": tool_response,
                "cwd": str(tmp_path),
            }
            exit_code, output = self._invoke("compress-read", payload, monkeypatch)
            assert exit_code == 0
            assert output == ""

    @staticmethod
    def _read_payload(path: Path, cwd: Path, text: str = "x = 1\n") -> dict:
        lines = len(text.splitlines())
        return {
            "hook_event_name": "PostToolUse",
            "tool_name": "Read",
            "tool_input": {"file_path": str(path)},
            "tool_response": {
                "type": "text",
                "file": {
                    "filePath": str(path),
                    "content": text,
                    "numLines": lines,
                    "startLine": 1,
                    "totalLines": lines,
                },
            },
            "cwd": str(cwd),
        }

    def test_compress_read_records_transitions_from_claude_codes_payload(
        self, monkeypatch, tmp_path
    ):
        # Claude Code nests a Read's text under file.content. The hook used to
        # look only for top-level keys, so real Reads never recorded a step.
        from neuralmind.namespaces import resolve_namespace
        from neuralmind.synapses import SynapseStore, default_db_path

        (tmp_path / ".neuralmind").mkdir()  # a project NeuralMind indexes
        first, second = tmp_path / "a.py", tmp_path / "b.py"
        for path in (first, second):
            self._invoke("compress-read", self._read_payload(path, tmp_path), monkeypatch)

        store = SynapseStore(
            default_db_path(str(tmp_path)), namespace=resolve_namespace(str(tmp_path))
        )
        edges = {(f, t) for f, t, _w, _c in store.transitions()}
        assert (str(first), str(second)) in edges

    def test_compress_read_records_only_text_reads_of_the_codebase(self, monkeypatch, tmp_path):
        import neuralmind.hooks as hooks_mod

        calls = []
        monkeypatch.setattr(hooks_mod, "_record_tool_transition", lambda *a: calls.append(a))
        image = {
            "tool_name": "Read",
            "tool_input": {"file_path": str(tmp_path / "logo.png")},
            "tool_response": {"type": "image", "file": {"base64": "iVBOR", "type": "image/png"}},
            "cwd": str(tmp_path),
        }
        kept_output = tmp_path / ".neuralmind" / "bash_outputs" / "0123456789abcdef.txt"
        for payload in (image, self._read_payload(kept_output, tmp_path)):
            exit_code, output = self._invoke("compress-read", payload, monkeypatch)
            assert (exit_code, output) == (0, "")
        assert calls == []

        # The flat shape older callers send still counts, in an indexed project.
        legacy = {
            "tool_name": "Read",
            "tool_input": {"file_path": "src/app.py"},
            "tool_response": {"content": "x = 1\n"},
            "cwd": str(tmp_path),
        }
        self._invoke("compress-read", legacy, monkeypatch)
        assert calls == []  # no .neuralmind/ yet: a global hook leaves the repo alone
        (tmp_path / ".neuralmind").mkdir(exist_ok=True)
        self._invoke("compress-read", legacy, monkeypatch)
        assert calls == [(str(tmp_path), "src/app.py")]

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

    def test_edit_activity_invokes_feedback(self, monkeypatch, tmp_path):
        """Edit/Write route to record_edit_activity and emit nothing."""
        import neuralmind.hooks as hooks_mod

        (tmp_path / ".neuralmind").mkdir()  # hooks act only in a built project
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
            "cwd": str(tmp_path),
        }
        exit_code, output = self._invoke("edit-activity", payload, monkeypatch)
        assert exit_code == 0
        assert output == ""  # pure side effect, emits nothing
        assert calls == [(str(tmp_path), "api/routes.py", "authenticate_user()")]

    def test_edit_activity_opt_out(self, monkeypatch, tmp_path):
        """NEURALMIND_REUSE_FEEDBACK=0 makes the branch a no-op."""
        import neuralmind.hooks as hooks_mod

        # A built project, so it's the env var — not the built-project gate —
        # that turns feedback off.
        (tmp_path / ".neuralmind").mkdir()
        monkeypatch.setenv("NEURALMIND_REUSE_FEEDBACK", "0")
        calls = []
        monkeypatch.setattr(hooks_mod, "_record_edit_activity", lambda *a: calls.append(a))
        payload = {
            "tool_name": "Write",
            "tool_input": {"file_path": "x.py", "content": "def f(): pass"},
            "tool_response": {},
            "cwd": str(tmp_path),
        }
        exit_code, output = self._invoke("edit-activity", payload, monkeypatch)
        assert exit_code == 0
        assert output == ""
        assert calls == []  # gated off — feedback never runs

    def test_compress_bash_populates_recovery_cache(self, monkeypatch, tmp_path):
        """The compress-bash hook stashes raw output to .neuralmind/last_output.json.

        This is what makes `neuralmind last` work: it shows the last command's
        output again without re-running it.
        """
        from neuralmind.output_cache import read_last_output

        (tmp_path / ".neuralmind").mkdir()  # an opted-in (built) project
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


INSTALL_LOG = "".join(
    f"Collecting pkg{n}\n  Downloading pkg{n}-1.0-py3-none-any.whl (12 kB)\n" for n in range(40)
) + (
    "Installing collected packages: " + ", ".join(f"pkg{n}" for n in range(40)) + "\n"
    "Successfully installed " + " ".join(f"pkg{n}-1.0" for n in range(40)) + "\n"
)


class TestBashReplaceOptIn:
    """NEURALMIND_BASH_REPLACE=1: trim allowlisted noisy logs via updatedToolOutput."""

    @pytest.fixture(autouse=True)
    def _indexed_project(self, tmp_path):
        # Hooks act only in a project that has opted in with `neuralmind build`.
        (tmp_path / ".neuralmind").mkdir()

    @staticmethod
    def _bash(command: str, stdout: str, cwd: Path, **extra) -> dict:
        # Claude Code's BashOutput: stdout, stderr, interrupted, isImage, ...
        response = {"stdout": stdout, "stderr": "", "interrupted": False, "isImage": False}
        response.update(extra)
        return {
            "hook_event_name": "PostToolUse",
            "tool_name": "Bash",
            "tool_input": {"command": command},
            "tool_response": response,
            "cwd": str(cwd),
        }

    def _run(self, action: str, payload: dict, monkeypatch) -> str:
        monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps(payload)))
        captured = io.StringIO()
        monkeypatch.setattr(sys, "stdout", captured)
        assert run_hook(action) == 0
        return captured.getvalue()

    def test_off_by_default(self, monkeypatch, tmp_path):
        monkeypatch.delenv("NEURALMIND_BASH_REPLACE", raising=False)
        payload = self._bash("pip install -r requirements.txt", INSTALL_LOG, tmp_path)
        assert self._run("compress-bash", payload, monkeypatch) == ""

    def test_trims_an_allowlisted_noisy_log(self, monkeypatch, tmp_path):
        monkeypatch.setenv("NEURALMIND_BASH_REPLACE", "1")
        payload = self._bash(
            "pip install -r requirements.txt",
            INSTALL_LOG,
            tmp_path,
            noOutputExpected=False,
            staleReadFileStateHint="requirements.txt changed",
        )
        response = json.loads(self._run("compress-bash", payload, monkeypatch))
        out = response["hookSpecificOutput"]
        assert out["hookEventName"] == "PostToolUse"
        assert "additionalContext" not in out
        replaced = out["updatedToolOutput"]
        # The Bash tool's output shape: the incoming result, with only the
        # streams swapped. Claude Code ignores a replacement that doesn't match.
        assert {k: v for k, v in replaced.items() if k not in ("stdout", "stderr")} == {
            k: v for k, v in payload["tool_response"].items() if k not in ("stdout", "stderr")
        }
        stdout = replaced["stdout"]
        assert not [
            ln for ln in stdout.splitlines() if "pkg0-1.0-py3" in ln or ln[:10] == "Collecting"
        ]
        assert "[neuralmind: 80 progress lines elided: Collecting ×40, Downloading ×40]" in stdout
        for line in INSTALL_LOG.splitlines()[-2:]:
            assert line in stdout.splitlines()
        assert len(stdout) < len(INSTALL_LOG) / 2

        # The note names a file holding the whole output.
        archive = Path(stdout.rsplit("Full output: ", 1)[1].rstrip("]\n"))
        assert archive.parent == tmp_path.resolve() / ".neuralmind" / "bash_outputs"
        assert INSTALL_LOG.rstrip() in archive.read_text()

    def test_note_follows_stderr_when_the_log_is_there(self, monkeypatch, tmp_path):
        monkeypatch.setenv("NEURALMIND_BASH_REPLACE", "1")
        progress = "".join(
            f"Embedding {n}/500 ({n // 5}%) · 0.0s elapsed, ~0.0s left · mod_py__fn_{n}\n"
            for n in range(1, 500, 25)
        )
        payload = self._bash("neuralmind build .", "Build successful!\n   Nodes: 500\n", tmp_path)
        payload["tool_response"]["stderr"] = progress
        replaced = json.loads(self._run("compress-bash", payload, monkeypatch))[
            "hookSpecificOutput"
        ]["updatedToolOutput"]
        assert replaced["stdout"] == "Build successful!\n   Nodes: 500\n"
        marker, note = replaced["stderr"].splitlines()
        assert marker == "[neuralmind: 20 progress lines elided: embedding progress ×20]"
        assert note.startswith("[neuralmind: neuralmind build progress lines elided where marked")

    def test_content_is_never_replaced(self, monkeypatch, tmp_path):
        monkeypatch.setenv("NEURALMIND_BASH_REPLACE", "1")
        for command in (
            "pytest -v",
            "git diff",
            "cat install.log",
            "pip list",
            "grep -rn Collecting .",
            "pip install -r requirements.txt && pytest -q",
            "pip install -r requirements.txt | tail -50",
        ):
            payload = self._bash(command, INSTALL_LOG, tmp_path)
            assert self._run("compress-bash", payload, monkeypatch) == "", command

    def test_unusual_results_are_left_alone(self, monkeypatch, tmp_path):
        monkeypatch.setenv("NEURALMIND_BASH_REPLACE", "1")
        cases = [
            {"interrupted": True},
            {"isImage": True},
            {"backgroundTaskId": "bash_1"},
            {"persistedOutputPath": "/tmp/tool-results/x.txt", "persistedOutputSize": 40_000},
        ]
        for extra in cases:
            payload = self._bash("pip install -r requirements.txt", INSTALL_LOG, tmp_path, **extra)
            assert self._run("compress-bash", payload, monkeypatch) == "", extra
        # No `interrupted` at all: not Claude Code's Bash shape.
        payload = self._bash("pip install -r requirements.txt", INSTALL_LOG, tmp_path)
        del payload["tool_response"]["interrupted"]
        assert self._run("compress-bash", payload, monkeypatch) == ""
        # Over the inline ceiling Claude Code shows a 2,000-character preview.
        big = INSTALL_LOG * 10
        assert len(big) > 30_000
        payload = self._bash("pip install -r requirements.txt", big, tmp_path)
        assert self._run("compress-bash", payload, monkeypatch) == ""

    def test_only_when_it_makes_the_result_smaller(self, monkeypatch, tmp_path):
        monkeypatch.setenv("NEURALMIND_BASH_REPLACE", "1")
        log = (
            "Requirement already satisfied: idna in ./v (from requests) (3.2)\n"
            "Requirement already satisfied: certifi in ./v (from requests) (2026.1)\n"
        )
        payload = self._bash("pip install requests", log, tmp_path)
        assert self._run("compress-bash", payload, monkeypatch) == ""

    def test_needs_somewhere_to_keep_the_full_output(self, monkeypatch, tmp_path):
        monkeypatch.setenv("NEURALMIND_BASH_REPLACE", "1")
        monkeypatch.setenv("NEURALMIND_OUTPUT_CACHE", "0")
        payload = self._bash("pip install -r requirements.txt", INSTALL_LOG, tmp_path)
        assert self._run("compress-bash", payload, monkeypatch) == ""

    def test_bypass_wins(self, monkeypatch, tmp_path):
        monkeypatch.setenv("NEURALMIND_BASH_REPLACE", "1")
        monkeypatch.setenv("NEURALMIND_BYPASS", "1")
        payload = self._bash("pip install -r requirements.txt", INSTALL_LOG, tmp_path)
        assert self._run("compress-bash", payload, monkeypatch) == ""

    def test_the_cache_still_holds_the_raw_output(self, monkeypatch, tmp_path):
        from neuralmind.output_cache import read_last_output

        monkeypatch.setenv("NEURALMIND_BASH_REPLACE", "1")
        payload = self._bash("pip install -r requirements.txt", INSTALL_LOG, tmp_path)
        assert self._run("compress-bash", payload, monkeypatch) != ""
        assert read_last_output(tmp_path)["stdout"] == INSTALL_LOG

    def test_read_and_grep_are_never_replaced(self, monkeypatch, tmp_path):
        monkeypatch.setenv("NEURALMIND_BASH_REPLACE", "1")
        path = tmp_path / "module.py"
        text = "def f():\n    return 1\n" * 200
        read = TestRunHook._read_payload(path, tmp_path, text)
        assert self._run("compress-read", read, monkeypatch) == ""
        grep = {
            "tool_name": "Grep",
            "tool_input": {"pattern": "def", "output_mode": "content"},
            "tool_response": {
                "mode": "content",
                "numFiles": 1,
                "filenames": ["module.py"],
                "content": "\n".join(f"module.py:{i}:def f():" for i in range(1, 400, 2)),
            },
        }
        assert self._run("cap-search", grep, monkeypatch) == ""


class TestHooksStayOutOfUnindexedProjects:
    """A hook never builds an index or creates `.neuralmind/` on its own.

    Hooks are often installed globally. prompt-submit used to fall through to
    a full first-time build (graph, IR, vectors) in whatever directory the
    session was opened in — minutes on a real repo, far past the hook
    timeout — and the other actions created `.neuralmind/` there as a side
    effect. `neuralmind build` is how a project opts in.
    """

    PAYLOADS = {
        "prompt-submit": {"prompt": "how does auth work?"},
        "session-start": {},
        "pre-compact": {},
        "stop": {},
        "session-end": {},
        "compress-bash": {
            "tool_input": {"command": "ls"},
            "tool_response": {"stdout": "a.py\n", "stderr": ""},
        },
        "compress-read": {
            "tool_input": {"file_path": "a.py"},
            "tool_response": {"content": "def f():\n    return 1\n"},
        },
        "edit-activity": {
            "tool_input": {"file_path": "a.py", "new_string": "def g():\n    return 2\n"},
        },
        "stale-guard": {"tool_input": {"file_path": "a.py"}},
    }

    def _run(self, action, payload, monkeypatch):
        monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps(payload)))
        captured = io.StringIO()
        monkeypatch.setattr(sys, "stdout", captured)
        return run_hook(action), captured.getvalue()

    @pytest.mark.parametrize("action", sorted(PAYLOADS))
    def test_unindexed_project_is_left_untouched(self, action, tmp_path, monkeypatch):
        (tmp_path / "a.py").write_text("def f():\n    return 1\n", encoding="utf-8")
        payload = {**self.PAYLOADS[action], "cwd": str(tmp_path)}

        code, out = self._run(action, payload, monkeypatch)

        assert code == 0
        assert out == ""
        assert not (tmp_path / ".neuralmind").exists()

    def test_prompt_submit_never_builds_in_an_opted_in_project(self, tmp_path, monkeypatch):
        """`.neuralmind/` alone (e.g. decisions only) is not an index to build."""
        (tmp_path / "a.py").write_text("def f():\n    return 1\n", encoding="utf-8")
        (tmp_path / ".neuralmind").mkdir()
        payload = {**self.PAYLOADS["prompt-submit"], "cwd": str(tmp_path)}

        builds = []

        def _no_build(self, *args, **kwargs):
            # Recorded, not raised: the hook fails open and would swallow it.
            builds.append(args)
            raise RuntimeError("a hook must never run a build")

        monkeypatch.setattr("neuralmind.core.NeuralMind.build", _no_build)
        code, out = self._run("prompt-submit", payload, monkeypatch)

        assert builds == []
        assert code == 0
        assert out == ""
        assert not (tmp_path / ".neuralmind" / "graph.json").exists()
        assert not (tmp_path / ".neuralmind" / "index_ir.json").exists()


class TestHookPayloadRobustness:
    """Hooks fail open: an odd payload never becomes a traceback and rc=1."""

    def _run(self, action, raw, monkeypatch):
        monkeypatch.setattr(sys, "stdin", io.StringIO(raw))
        captured = io.StringIO()
        monkeypatch.setattr(sys, "stdout", captured)
        return run_hook(action), captured.getvalue()

    @pytest.mark.parametrize("raw", ["[]", '"text"', "42", "null"])
    def test_non_object_payload_is_ignored(self, raw, monkeypatch):
        assert self._run("prompt-submit", raw, monkeypatch) == (0, "")

    def test_bypass_holds_for_a_payload_it_cannot_use(self, monkeypatch):
        monkeypatch.setenv("NEURALMIND_BYPASS", "1")
        assert self._run("prompt-submit", "[]", monkeypatch) == (0, "")

    @pytest.mark.parametrize(
        "action, payload",
        [
            ("compress-read", {"tool_input": "x", "tool_response": "y"}),
            ("edit-activity", {"tool_input": ["a.py"], "tool_response": {}}),
            ("prompt-submit", {"prompt": 123}),
            ("compress-bash", {"tool_response": {"stdout": "x", "exit_code": "abc"}}),
            ("stale-guard", {"tool_input": {"file_path": 7}}),
        ],
    )
    def test_wrongly_typed_fields_fail_open(self, action, payload, tmp_path, monkeypatch):
        (tmp_path / ".neuralmind").mkdir()
        raw = json.dumps({**payload, "cwd": str(tmp_path)})
        code, out = self._run(action, raw, monkeypatch)
        assert code == 0
        assert out == ""


class TestHookProjectRoot:
    """After the agent runs `cd sub/`, hooks still act on the project.

    The payload's cwd follows the agent's shell, so a session in a built
    project went silent (or wrote a stray sub/.neuralmind/) once it changed
    directory. The root is the nearest directory with `.neuralmind/`, looked
    for no higher than $CLAUDE_PROJECT_DIR.
    """

    def _edit(self, cwd, file_path, monkeypatch):
        import neuralmind.hooks as hooks_mod

        calls = []
        monkeypatch.setattr(
            hooks_mod, "_record_edit_activity", lambda root, fp, code: calls.append((root, fp))
        )
        monkeypatch.setattr(hooks_mod, "_record_tool_transition", lambda *a: None)
        payload = {
            "tool_input": {"file_path": file_path, "new_string": "def f():\n    pass\n"},
            "tool_response": {},
            "cwd": str(cwd),
        }
        monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps(payload)))
        monkeypatch.setattr(sys, "stdout", io.StringIO())
        assert run_hook("edit-activity") == 0
        return calls

    def test_subdirectory_resolves_to_the_project(self, tmp_path, monkeypatch):
        (tmp_path / ".neuralmind").mkdir()
        sub = tmp_path / "auth"
        sub.mkdir()
        monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(tmp_path))

        calls = self._edit(sub, "handlers.py", monkeypatch)

        # A relative path was relative to the session's cwd: rebased onto the root.
        assert calls == [(str(tmp_path), os.path.join("auth", "handlers.py"))]
        assert not (sub / ".neuralmind").exists()

    def test_without_claude_project_dir_only_cwd_counts(self, tmp_path, monkeypatch):
        (tmp_path / ".neuralmind").mkdir()
        sub = tmp_path / "auth"
        sub.mkdir()
        monkeypatch.delenv("CLAUDE_PROJECT_DIR", raising=False)

        assert self._edit(sub, "handlers.py", monkeypatch) == []

    def test_walk_never_leaves_claude_project_dir(self, tmp_path, monkeypatch):
        (tmp_path / ".neuralmind").mkdir()  # above the session's project
        project = tmp_path / "repo"
        sub = project / "pkg"
        sub.mkdir(parents=True)
        monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(project))

        assert self._edit(sub, "a.py", monkeypatch) == []


class TestReadTransitionsWithClaudeCodePayload:
    """Read transitions are recorded from Claude Code's real Read output.

    Claude Code nests a text read under tool_response.file.content; the hook
    only looked at a flat `content`, saw nothing, and returned before
    recording the transition.
    """

    def test_nested_read_payload_records_a_transition(self, tmp_path, monkeypatch):
        from neuralmind.synapses import SynapseStore, default_db_path

        (tmp_path / ".neuralmind").mkdir()
        monkeypatch.delenv("NEURALMIND_NO_LEARN", raising=False)
        monkeypatch.setenv("NEURALMIND_READ_DEDUP", "0")
        for name in ("a.py", "b.py"):
            path = str(tmp_path / name)
            payload = {
                "tool_name": "Read",
                "tool_input": {"file_path": path},
                "tool_response": {
                    "type": "text",
                    "file": {"filePath": path, "content": "x = 1\n", "numLines": 1},
                },
                "cwd": str(tmp_path),
            }
            monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps(payload)))
            monkeypatch.setattr(sys, "stdout", io.StringIO())
            assert run_hook("compress-read") == 0

        store = SynapseStore(default_db_path(str(tmp_path)))
        assert store.get_meta("_last_touched_file") == str(tmp_path / "b.py")
