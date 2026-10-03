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

        # The flat shape older callers send still counts.
        legacy = {
            "tool_name": "Read",
            "tool_input": {"file_path": "src/app.py"},
            "tool_response": {"content": "x = 1\n"},
            "cwd": "/proj",
        }
        self._invoke("compress-read", legacy, monkeypatch)
        assert calls == [("/proj", "src/app.py")]

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

        This is what makes `neuralmind last` work: it shows the last command's
        output again without re-running it.
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


INSTALL_LOG = "".join(
    f"Collecting pkg{n}\n  Downloading pkg{n}-1.0-py3-none-any.whl (12 kB)\n" for n in range(40)
) + (
    "Installing collected packages: " + ", ".join(f"pkg{n}" for n in range(40)) + "\n"
    "Successfully installed " + " ".join(f"pkg{n}-1.0" for n in range(40)) + "\n"
)


class TestBashReplaceOptIn:
    """NEURALMIND_BASH_REPLACE=1: trim allowlisted noisy logs via updatedToolOutput."""

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
