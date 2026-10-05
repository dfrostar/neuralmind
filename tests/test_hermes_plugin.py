"""Tests for the Hermes-Agent plugin and its installer.

Hermes isn't needed: the plugin's hooks are plain functions Hermes calls with
keyword arguments (``pre_llm_call``: session_id, user_message, is_first_turn,
parent_session_id …; ``post_tool_call``: tool_name, args, result, session_id …),
so the tests call them the same way. One round trip runs the real
``python -m neuralmind _hook`` subprocess.
"""

from __future__ import annotations

import json
import sys
import threading
from pathlib import Path

import pytest

from neuralmind import hermes_install
from neuralmind import hermes_plugin as plugin


def _built(path: Path) -> Path:
    (path / ".neuralmind").mkdir(parents=True, exist_ok=True)
    (path / ".neuralmind" / "build_status.json").write_text("{}")
    return path


@pytest.fixture(autouse=True)
def _isolate(monkeypatch, tmp_path):
    for var in ("NEURALMIND_PROJECT", "TERMINAL_CWD", "NEURALMIND_BYPASS"):
        monkeypatch.delenv(var, raising=False)
    # No installed config.json next to the plugin module.
    monkeypatch.setattr(plugin, "_config", dict)
    monkeypatch.chdir(tmp_path)


@pytest.fixture
def calls(monkeypatch):
    """Record _run calls instead of starting subprocesses."""
    recorded: list[tuple[str, dict]] = []

    def fake_run(action, payload):
        recorded.append((action, payload))
        return {"session-start": "RECAP", "prompt-submit": "RECALL"}.get(action, "")

    monkeypatch.setattr(plugin, "_run", fake_run)
    return recorded


@pytest.fixture
def sync_threads(monkeypatch):
    class Inline:
        def __init__(self, target, daemon=None):
            self._target = target

        def start(self):
            self._target()

    monkeypatch.setattr(threading, "Thread", Inline)


def test_register_wires_both_hooks():
    registered = {}

    class Ctx:
        def register_hook(self, name, callback):
            registered[name] = callback

    plugin.register(Ctx())
    assert registered == {
        "pre_llm_call": plugin.on_pre_llm_call,
        "post_tool_call": plugin.on_post_tool_call,
    }


def test_nothing_happens_outside_a_built_project(tmp_path, calls):
    assert plugin.on_pre_llm_call(session_id="s", user_message="hi", is_first_turn=True) is None
    plugin.on_post_tool_call(tool_name="write_file", args={"path": "a.py"}, session_id="s")
    assert calls == []


def test_project_precedence(tmp_path, monkeypatch):
    env, config, terminal, cwd = (_built(tmp_path / n) for n in ("env", "cfg", "term", "cwd"))
    monkeypatch.chdir(cwd)
    assert plugin._project() == cwd
    monkeypatch.setenv("TERMINAL_CWD", str(terminal))
    assert plugin._project() == terminal
    monkeypatch.setattr(plugin, "_config", lambda: {"project": str(config)})
    assert plugin._project() == config
    monkeypatch.setenv("NEURALMIND_PROJECT", str(env))
    assert plugin._project() == env


def test_an_unbuilt_candidate_falls_through(tmp_path, monkeypatch):
    unbuilt = tmp_path / "unbuilt"
    unbuilt.mkdir()
    monkeypatch.setenv("NEURALMIND_PROJECT", str(unbuilt))
    built = _built(tmp_path / "built")
    monkeypatch.chdir(built)
    assert plugin._project() == built


def test_first_turn_gets_recap_then_recall(tmp_path, calls):
    _built(tmp_path)
    result = plugin.on_pre_llm_call(
        session_id="s1", user_message="how does auth work?", is_first_turn=True
    )
    assert result == {"context": "RECAP\n\nRECALL"}
    assert calls == [
        ("session-start", {"cwd": str(tmp_path), "session_id": "s1", "source": "startup"}),
        (
            "prompt-submit",
            {"cwd": str(tmp_path), "session_id": "s1", "prompt": "how does auth work?"},
        ),
    ]


def test_later_turns_get_recall_only(tmp_path, calls):
    _built(tmp_path)
    result = plugin.on_pre_llm_call(session_id="s1", user_message="next", is_first_turn=False)
    assert result == {"context": "RECALL"}
    assert [a for a, _ in calls] == ["prompt-submit"]


def test_nothing_to_add_returns_none(tmp_path, monkeypatch):
    _built(tmp_path)
    monkeypatch.setattr(plugin, "_run", lambda action, payload: "")
    assert plugin.on_pre_llm_call(session_id="s", user_message="x", is_first_turn=True) is None


def test_subagent_turns_are_ignored(tmp_path, calls):
    _built(tmp_path)
    out = plugin.on_pre_llm_call(
        session_id="child", user_message="do X", is_first_turn=True, parent_session_id="s1"
    )
    assert out is None and calls == []


def test_multimodal_message_text_is_used(tmp_path, calls):
    _built(tmp_path)
    message = [{"type": "text", "text": "explain this"}, {"type": "image_url", "image_url": {}}]
    plugin.on_pre_llm_call(session_id="s", user_message=message, is_first_turn=False)
    assert calls[0][1]["prompt"] == "explain this"


def test_unknown_kwargs_are_accepted(tmp_path, calls):
    _built(tmp_path)
    assert plugin.on_pre_llm_call(
        session_id="s",
        user_message="x",
        is_first_turn=False,
        telemetry_schema_version=3,
        sender_id="u",
        turn_id="t",
    ) == {"context": "RECALL"}


def test_write_file_records_the_edit(tmp_path, calls, sync_threads):
    _built(tmp_path)
    plugin.on_post_tool_call(
        tool_name="write_file",
        args={"path": "src/app.py", "content": "x = 1\n"},
        result='{"bytes_written": 6}',
        session_id="s1",
    )
    assert calls == [
        (
            "edit-activity",
            {
                "cwd": str(tmp_path),
                "session_id": "s1",
                "tool_input": {
                    "file_path": str(tmp_path / "src" / "app.py"),
                    "new_string": "x = 1\n",
                },
            },
        )
    ]


def test_v4a_patch_records_each_file(tmp_path, calls, sync_threads):
    _built(tmp_path)
    patch = (
        "*** Begin Patch\n*** Update File: a.py\n@@\n-x\n+y\n"
        "*** Add File: docs/b.md\n+hello\n*** End Patch\n"
    )
    plugin.on_post_tool_call(
        tool_name="patch", args={"mode": "patch", "patch": patch}, session_id="s1"
    )
    assert [p["tool_input"]["file_path"] for _, p in calls] == [
        str(tmp_path / "a.py"),
        str(tmp_path / "docs" / "b.md"),
    ]


def test_relative_paths_resolve_like_hermes_does(tmp_path, monkeypatch, calls, sync_threads):
    project = _built(tmp_path / "pinned")
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    monkeypatch.setenv("NEURALMIND_PROJECT", str(project))
    monkeypatch.setenv("TERMINAL_CWD", str(workspace))
    plugin.on_post_tool_call(tool_name="write_file", args={"path": "a.py"}, session_id="s1")
    assert calls[0][1]["cwd"] == str(project)
    assert calls[0][1]["tool_input"]["file_path"] == str(workspace / "a.py")


@pytest.mark.parametrize(
    "kwargs",
    [
        {"tool_name": "terminal", "args": {"command": "ls"}},
        {"tool_name": "write_file", "args": {"path": "a.py"}, "result": '{"error": "denied"}'},
        {"tool_name": "write_file", "args": {"path": "a.py"}, "parent_session_id": "p"},
        {"tool_name": "write_file", "args": "not a dict"},
    ],
)
def test_edits_not_recorded(tmp_path, calls, sync_threads, kwargs):
    _built(tmp_path)
    plugin.on_post_tool_call(session_id="s1", **kwargs)
    assert calls == []


def test_child_env_drops_hermes_python_setup(monkeypatch):
    monkeypatch.setenv("PYTHONPATH", "/hermes/site-packages")
    monkeypatch.setenv("VIRTUAL_ENV", "/hermes/venv")
    monkeypatch.setenv("NEURALMIND_SESSION_RECAP", "0")
    env = plugin._child_env()
    assert "PYTHONPATH" not in env and "VIRTUAL_ENV" not in env
    assert env["NEURALMIND_SESSION_RECAP"] == "0"


def test_run_fails_open(monkeypatch):
    monkeypatch.setattr(plugin, "_python", lambda: "/nonexistent/python")
    assert plugin._run("prompt-submit", {}) == ""


def test_real_round_trip_recap_reaches_hermes(tmp_path, monkeypatch):
    """Through the real `python -m neuralmind _hook` subprocess."""
    _built(tmp_path)
    monkeypatch.setattr(plugin, "_python", lambda: sys.executable)
    monkeypatch.setenv("NEURALMIND_SYNAPSE_INJECT", "0")
    monkeypatch.setenv("NEURALMIND_SYNAPSE_EXPORT", "0")
    monkeypatch.setenv("NEURALMIND_PROVENANCE_INJECT", "0")
    monkeypatch.setenv("PYTHONPATH", "/somewhere/hermes/site-packages")
    monkeypatch.setenv(plugin.TIMEOUT_ENV, "60")
    first = plugin.on_pre_llm_call(
        session_id="h1", user_message="add retry logic to the uploader", is_first_turn=True
    )
    assert first is None  # nothing to recap or recall yet
    second = plugin.on_pre_llm_call(
        session_id="h2", user_message="where were we?", is_first_turn=True
    )
    assert second is not None
    assert "NeuralMind session recap" in second["context"]
    assert '"add retry logic to the uploader"' in second["context"]


# --- installer -------------------------------------------------------------


def test_install_writes_plugin_files(tmp_path):
    home = tmp_path / "hermes"
    home.mkdir()
    project = _built(tmp_path / "proj")
    result = hermes_install.install(str(project), home=home, enable=False)
    target = home / "plugins" / "neuralmind"
    assert result["path"] == target and result["built"] is True and result["enabled"] is None
    assert (target / "__init__.py").read_text() == Path(plugin.__file__).read_text()
    manifest = (target / "plugin.yaml").read_text()
    assert "name: neuralmind" in manifest
    assert "  - pre_llm_call" in manifest and "  - post_tool_call" in manifest
    config = json.loads((target / "config.json").read_text())
    assert config == {"python": sys.executable, "project": str(project.resolve())}


def test_install_without_project_and_unbuilt_project(tmp_path):
    home = tmp_path / "hermes"
    home.mkdir()
    assert hermes_install.install(None, home=home, enable=False)["project"] is None
    unbuilt = tmp_path / "raw"
    unbuilt.mkdir()
    assert hermes_install.install(str(unbuilt), home=home, enable=False)["built"] is False


def test_install_needs_a_hermes_home(tmp_path):
    with pytest.raises(FileNotFoundError):
        hermes_install.install(None, home=tmp_path / "missing", enable=False)


def test_enable_runs_hermes_with_the_home(tmp_path, monkeypatch):
    home = tmp_path / "hermes"
    home.mkdir()
    seen = {}

    class Done:
        returncode = 0

    def fake_run(command, env, **kwargs):
        seen["command"], seen["home"] = command, env["HERMES_HOME"]
        return Done()

    monkeypatch.setattr(hermes_install.shutil, "which", lambda name: "/bin/hermes")
    monkeypatch.setattr(hermes_install.subprocess, "run", fake_run)
    assert hermes_install.install(None, home=home)["enabled"] is True
    assert seen["command"] == [
        "/bin/hermes",
        "plugins",
        "enable",
        "neuralmind",
        "--no-allow-tool-override",
    ]
    assert seen["home"] == str(home)


def test_enable_skipped_without_hermes_on_path(tmp_path, monkeypatch):
    home = tmp_path / "hermes"
    home.mkdir()
    monkeypatch.setattr(hermes_install.shutil, "which", lambda name: None)
    assert hermes_install.install(None, home=home)["enabled"] is None


def test_uninstall_removes_the_plugin(tmp_path, monkeypatch):
    home = tmp_path / "hermes"
    home.mkdir()
    monkeypatch.setattr(hermes_install.shutil, "which", lambda name: None)
    hermes_install.install(None, home=home, enable=False)
    result = hermes_install.uninstall(home)
    assert result["removed"] is True
    assert not (home / "plugins" / "neuralmind").exists()
    assert hermes_install.uninstall(home)["removed"] is False


def test_cli_install_and_uninstall(tmp_path, capsys, monkeypatch):
    from neuralmind.cli import main

    home = tmp_path / "hermes"
    home.mkdir()
    project = _built(tmp_path / "proj")
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "neuralmind",
            "install-hermes-plugin",
            str(project),
            "--no-enable",
            "--hermes-home",
            str(home),
        ],
    )
    main()
    out = capsys.readouterr().out
    assert "NeuralMind plugin installed" in out and str(project.resolve()) in out
    monkeypatch.setattr(
        sys,
        "argv",
        ["neuralmind", "install-hermes-plugin", "--uninstall", "--hermes-home", str(home)],
    )
    monkeypatch.setattr(hermes_install.shutil, "which", lambda name: None)
    main()
    assert "Removed the NeuralMind plugin" in capsys.readouterr().out
