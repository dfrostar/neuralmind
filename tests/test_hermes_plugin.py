"""Tests for the Hermes-Agent plugin and its installer.

Hermes isn't needed: the plugin's hooks are plain functions Hermes calls with
keyword arguments (``pre_llm_call``: session_id, user_message, is_first_turn,
parent_session_id …; ``post_tool_call``: tool_name, args, result, session_id …),
so the tests call them the same way. One round trip runs the real
``python -m neuralmind _hook`` subprocess.
"""

from __future__ import annotations

import json
import logging
import os
import re
import shutil
import sys
import threading
from pathlib import Path
from types import SimpleNamespace

import pytest

from neuralmind import hermes_install
from neuralmind import hermes_plugin as plugin

REPO_ROOT = Path(__file__).resolve().parents[1]
PLUGIN_SOURCE = Path(plugin.__file__).parent


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
    monkeypatch.setattr(plugin, "_SUBAGENT_SESSIONS", {})
    monkeypatch.setattr(plugin, "_SUBAGENT_TASKS", {})
    monkeypatch.setattr(plugin, "_WARNED", set())
    # The once-per-process version check runs its own subprocess; tested below.
    monkeypatch.setattr(plugin, "_version_checked", True)
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


def test_subagent_edits_are_not_recorded(tmp_path, calls, sync_threads):
    # Hermes's post_tool_call has no parent_session_id: the subagent is known by
    # the session id its own pre_llm_call reported first.
    _built(tmp_path)
    plugin.on_pre_llm_call(
        session_id="child", user_message="do X", is_first_turn=True, parent_session_id="s1"
    )
    plugin.on_post_tool_call(tool_name="write_file", args={"path": "a.py"}, session_id="child")
    plugin.on_post_tool_call(tool_name="write_file", args={"path": "b.py"}, session_id="s1")
    assert [p["session_id"] for _, p in calls] == ["s1"]


def test_hermes_error_status_is_not_recorded(tmp_path, calls, sync_threads):
    _built(tmp_path)
    plugin.on_post_tool_call(
        tool_name="patch",
        args={"path": "a.py", "old_string": "x", "new_string": "y"},
        result="Error: no match",
        status="error",
        session_id="s1",
    )
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
    # Like Hermes's launcher: a PYTHONPATH whose packages break NeuralMind's
    # interpreter. The child only works if _run strips it.
    poison = tmp_path / "hermes-site-packages" / "neuralmind"
    poison.mkdir(parents=True)
    (poison / "__init__.py").write_text("raise ImportError('Hermes site-packages leaked')\n")
    monkeypatch.setenv("PYTHONPATH", str(poison.parent))
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
    # The committed manifest, the one Hermes reads when it installs from a clone.
    assert (target / "plugin.yaml").read_text() == (PLUGIN_SOURCE / "plugin.yaml").read_text()
    assert result["managed"] is False
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
    (home / "config.yaml").write_text("model: x\n")
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
        "-p",
        "default",
        "plugins",
        "enable",
        "neuralmind",
        "--no-allow-tool-override",
    ]
    assert seen["home"] == str(home)


def test_never_enables_in_an_uninitialised_home(tmp_path, monkeypatch):
    # `hermes plugins enable` in an empty home runs Hermes's first-run setup,
    # which rewrites the shared Hermes launchers to point at that directory.
    home = tmp_path / "hermes"
    home.mkdir()
    monkeypatch.setattr(hermes_install.shutil, "which", lambda name: "/bin/hermes")

    def boom(*args, **kwargs):
        raise AssertionError("hermes must not run against an uninitialised home")

    monkeypatch.setattr(hermes_install.subprocess, "run", boom)
    result = hermes_install.install(None, home=home)
    assert result["enabled"] is None and result["initialised"] is False


def test_rerun_keeps_the_pinned_project_and_unpin_clears_it(tmp_path):
    home = tmp_path / "hermes"
    home.mkdir()
    project = _built(tmp_path / "proj")
    hermes_install.install(str(project), home=home, enable=False)
    assert hermes_install.install(None, home=home, enable=False)["project"] == str(
        project.resolve()
    )
    assert hermes_install.install(None, home=home, enable=False, unpin=True)["project"] is None
    config = json.loads((home / "plugins" / "neuralmind" / "config.json").read_text())
    assert config["project"] is None


def test_default_hermes_home_follows_hermes(monkeypatch, tmp_path):
    monkeypatch.delenv("HERMES_HOME", raising=False)
    monkeypatch.delenv("HERMES_DATA_DIR_SUFFIX", raising=False)
    monkeypatch.setattr(hermes_install.sys, "platform", "darwin")
    assert hermes_install.hermes_home() == Path.home() / ".hermes"
    monkeypatch.setattr(hermes_install.sys, "platform", "win32")
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    assert hermes_install.hermes_home() == tmp_path / "hermes"
    monkeypatch.setenv("HERMES_HOME", str(tmp_path / "custom"))
    assert hermes_install.hermes_home() == tmp_path / "custom"


def test_enable_skipped_without_hermes_on_path(tmp_path, monkeypatch):
    home = tmp_path / "hermes"
    home.mkdir()
    (home / "config.yaml").write_text("model: x\n")
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


def test_unbuilt_terminal_cwd_means_no_project(tmp_path, monkeypatch, calls):
    # Hermes works in TERMINAL_CWD; the directory the process started in
    # (built or not) must not stand in for it.
    built = _built(tmp_path / "started-here")
    unbuilt = tmp_path / "autopilot"
    unbuilt.mkdir()
    monkeypatch.chdir(built)
    monkeypatch.setenv("TERMINAL_CWD", str(unbuilt))
    assert plugin._project() is None
    assert plugin.on_pre_llm_call(session_id="s", user_message="x", is_first_turn=True) is None
    assert calls == []


def test_subagent_edits_skipped_after_session_rotation(tmp_path, calls, sync_threads):
    _built(tmp_path)
    plugin.on_pre_llm_call(
        session_id="child-1",
        user_message="do X",
        is_first_turn=True,
        parent_session_id="s1",
        task_id="task-9",
    )
    # Hermes rotated the subagent's session id (context compression); task_id stays.
    plugin.on_post_tool_call(
        tool_name="write_file", args={"path": "a.py"}, session_id="child-2", task_id="task-9"
    )
    assert calls == []


def test_paths_hermes_reports_are_used(tmp_path, monkeypatch, calls, sync_threads):
    _built(tmp_path)
    monkeypatch.setenv("TERMINAL_CWD", str(tmp_path))
    written = str(tmp_path / "src" / "util.py")  # the agent had `cd src`'d
    plugin.on_post_tool_call(
        tool_name="write_file",
        args={"path": "util.py", "content": "x"},
        result=json.dumps({"bytes_written": 1, "files_modified": [written]}),
        session_id="s1",
    )
    assert [p["tool_input"]["file_path"] for _, p in calls] == [written]


def test_uninstall_never_runs_hermes_in_an_uninitialised_home(tmp_path, monkeypatch):
    home = tmp_path / "hermes"
    home.mkdir()
    hermes_install.install(None, home=home, enable=False)
    monkeypatch.setattr(hermes_install.shutil, "which", lambda name: "/bin/hermes")

    def boom(*args, **kwargs):
        raise AssertionError("hermes must not run against an uninitialised home")

    monkeypatch.setattr(hermes_install.subprocess, "run", boom)
    result = hermes_install.uninstall(home)
    assert result["removed"] is True and result["disabled"] is None


@pytest.mark.parametrize("status", ["cancelled", "timeout", "blocked"])
def test_edits_that_did_not_land_are_not_recorded(tmp_path, calls, sync_threads, status):
    _built(tmp_path)
    plugin.on_post_tool_call(
        tool_name="write_file",
        args={"path": "never_written.py", "content": "x"},
        result="[Tool execution cancelled — write_file was skipped due to user interrupt]",
        status=status,
        session_id="s1",
    )
    assert calls == []


def test_cron_turns_are_not_the_users(tmp_path, calls, sync_threads):
    _built(tmp_path)
    out = plugin.on_pre_llm_call(
        session_id="cron-1",
        user_message="Summarise today's front page",
        is_first_turn=True,
        platform="cron",
        task_id="cron-task",
    )
    assert out is None
    plugin.on_post_tool_call(
        tool_name="write_file", args={"path": "a.py"}, session_id="cron-1", task_id="cron-task"
    )
    assert calls == []


def test_deleted_files_are_not_listed_as_edited(tmp_path, calls, sync_threads):
    _built(tmp_path)
    kept, gone = str(tmp_path / "a.py"), str(tmp_path / "old.py")
    plugin.on_post_tool_call(
        tool_name="patch",
        args={"mode": "patch", "patch": "..."},
        result=json.dumps(
            {"success": True, "files_modified": [kept, gone], "files_deleted": [gone]}
        ),
        status="ok",
        session_id="s1",
    )
    assert [p["tool_input"]["file_path"] for _, p in calls] == [kept]


def test_skip_lists_evict_oldest(monkeypatch):
    monkeypatch.setattr(plugin, "_SUBAGENT_SESSIONS_MAX", 3)
    ids: dict = {}
    for key in ("a", "b", "c", "d"):
        plugin._remember(ids, key)
    assert list(ids) == ["b", "c", "d"]


def test_install_targets_the_active_profile(tmp_path, monkeypatch):
    monkeypatch.delenv("HERMES_HOME", raising=False)
    monkeypatch.delenv("HERMES_DATA_DIR_SUFFIX", raising=False)
    monkeypatch.setattr(hermes_install.sys, "platform", "darwin")
    monkeypatch.setattr(hermes_install.Path, "home", lambda: tmp_path)
    root = tmp_path / ".hermes"
    (root / "profiles" / "work").mkdir(parents=True)
    assert hermes_install.hermes_home() == root
    (root / "active_profile").write_text("work\n")
    assert hermes_install.hermes_home() == root / "profiles" / "work"
    (root / "active_profile").write_text("default\n")
    assert hermes_install.hermes_home() == root


def test_profile_home_is_passed_without_p_default(tmp_path, monkeypatch):
    home = tmp_path / "profiles" / "work"
    home.mkdir(parents=True)
    (home / "config.yaml").write_text("model: x\n")
    seen = {}

    class Done:
        returncode = 0

    def fake_run(command, env, **kwargs):
        seen["command"] = command
        return Done()

    monkeypatch.setattr(hermes_install.shutil, "which", lambda name: "/bin/hermes")
    monkeypatch.setattr(hermes_install.subprocess, "run", fake_run)
    hermes_install.install(None, home=home)
    assert "-p" not in seen["command"]


def test_rerun_does_not_re_enable_a_disabled_plugin(tmp_path, monkeypatch):
    home = tmp_path / "hermes"
    home.mkdir()
    hermes_install.install(None, home=home, enable=False)  # installed earlier …
    # … and switched off since with `hermes plugins disable neuralmind`.
    (home / "config.yaml").write_text("plugins:\n  enabled: []\n  disabled:\n    - neuralmind\n")
    monkeypatch.setattr(hermes_install.shutil, "which", lambda name: "/bin/hermes")

    def boom(*args, **kwargs):
        raise AssertionError("must not re-enable a plugin the user disabled")

    monkeypatch.setattr(hermes_install.subprocess, "run", boom)
    result = hermes_install.install(None, home=home)
    assert result["enabled"] is None and result["disabled_by_user"] is True


def test_install_refuses_a_symlinked_plugin_dir_and_uninstall_unlinks_it(tmp_path):
    home = tmp_path / "hermes"
    (home / "plugins").mkdir(parents=True)
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    (elsewhere / "keep.txt").write_text("x")
    try:
        (home / "plugins" / "neuralmind").symlink_to(elsewhere, target_is_directory=True)
    except (OSError, NotImplementedError):
        pytest.skip("symlinks unavailable")
    with pytest.raises(FileExistsError):
        hermes_install.install(None, home=home, enable=False)
    result = hermes_install.uninstall(home)
    assert result["removed"] is True
    assert not (home / "plugins" / "neuralmind").exists()
    assert (elsewhere / "keep.txt").exists()


def test_cli_uninstall_of_an_uninitialised_home_gives_no_path_hint(tmp_path, capsys, monkeypatch):
    from neuralmind.cli import main

    home = tmp_path / "hermes"
    home.mkdir()
    hermes_install.install(None, home=home, enable=False)
    monkeypatch.setattr(hermes_install.shutil, "which", lambda name: "/bin/hermes")
    monkeypatch.setattr(
        sys,
        "argv",
        ["neuralmind", "install-hermes-plugin", "--uninstall", "--hermes-home", str(home)],
    )
    main()
    out = capsys.readouterr().out
    assert "Removed the NeuralMind plugin" in out and "isn't on PATH" not in out


def test_a_patch_that_changed_nothing_is_not_recorded(tmp_path, calls, sync_threads):
    _built(tmp_path)
    plugin.on_post_tool_call(
        tool_name="patch",
        args={"path": "a.py", "old_string": "x", "new_string": "x"},
        result=json.dumps(
            {"success": True, "no_change": True, "files_modified": [str(tmp_path / "a.py")]}
        ),
        status="ok",
        session_id="s1",
    )
    assert calls == []


def test_v4a_deletes_and_move_sources_are_not_listed(tmp_path, calls, sync_threads):
    _built(tmp_path)
    patch = (
        "*** Begin Patch\n*** Update File: src/a.py\n@@\n-x\n+y\n"
        "*** Delete File: src/old.py\n*** Move File: src/from.py -> src/to.py\n*** End Patch\n"
    )
    written = [str(tmp_path / "src" / n) for n in ("a.py", "old.py", "from.py", "to.py")]
    plugin.on_post_tool_call(
        tool_name="patch",
        args={"mode": "patch", "patch": patch},
        # files_deleted spelled as the raw header, files_modified resolved
        result=json.dumps(
            {"success": True, "files_modified": written, "files_deleted": ["src/old.py"]}
        ),
        status="ok",
        session_id="s1",
    )
    assert [p["tool_input"]["file_path"] for _, p in calls] == [written[0], written[3]]


def test_a_hermes_home_root_still_follows_the_active_profile(tmp_path, monkeypatch):
    root = tmp_path / "custom-root"
    (root / "profiles" / "work").mkdir(parents=True)
    (root / "active_profile").write_text("work\n")
    monkeypatch.setenv("HERMES_HOME", str(root))
    assert hermes_install.hermes_home() == root / "profiles" / "work"
    monkeypatch.setenv("HERMES_HOME", str(root / "profiles" / "work"))
    assert hermes_install.hermes_home() == root / "profiles" / "work"


@pytest.mark.parametrize(
    ("deleted", "kept_name"), [("a.py", "data.py"), (".env", "env"), ("./src/x.py", "src/ax.py")]
)
def test_deleted_file_does_not_hide_a_similar_name(
    tmp_path, calls, sync_threads, deleted, kept_name
):
    _built(tmp_path)
    kept = str(tmp_path / kept_name)
    gone = str(tmp_path / deleted.lstrip("./") if deleted.startswith("./") else tmp_path / deleted)
    plugin.on_post_tool_call(
        tool_name="patch",
        args={
            "mode": "patch",
            "patch": f"*** Begin Patch\n*** Delete File: {deleted}\n*** End Patch\n",
        },
        result=json.dumps(
            {"success": True, "files_modified": [kept, gone], "files_deleted": [deleted]}
        ),
        status="ok",
        session_id="s1",
    )
    assert [p["tool_input"]["file_path"] for _, p in calls] == [kept]


def test_a_project_cannot_shadow_the_installed_package(tmp_path, monkeypatch):
    """A served repository with its own `neuralmind` must not run in the hook."""
    project = _built(tmp_path / "repo")
    evil = project / "neuralmind"
    evil.mkdir()
    marker = tmp_path / "pwned"
    (evil / "__init__.py").write_text(f"open({str(marker)!r}, 'w').write('x')\n")
    (evil / "__main__.py").write_text(f"open({str(marker)!r}, 'w').write('x')\n")
    (project / "neuralmind.py").write_text(f"open({str(marker)!r}, 'w').write('x')\n")
    monkeypatch.chdir(project)
    monkeypatch.setattr(plugin, "_python", lambda: sys.executable)
    monkeypatch.setenv(plugin.TIMEOUT_ENV, "60")
    plugin._run("session-start", {"cwd": str(project), "session_id": "s", "source": "resume"})
    assert not marker.exists()


def test_v4a_patch_gives_each_file_only_its_own_code(tmp_path, calls, sync_threads):
    _built(tmp_path)
    patch = (
        "*** Begin Patch\n*** Update File: src/a.py\n@@\n-old_a()\n+new_a_function()\n"
        "*** Add File: src/b.py\n+def only_in_b():\n+    pass\n*** End Patch\n"
    )
    written = [str(tmp_path / "src" / "a.py"), str(tmp_path / "src" / "b.py")]
    plugin.on_post_tool_call(
        tool_name="patch",
        args={"mode": "patch", "patch": patch},
        result=json.dumps({"success": True, "files_modified": written}),
        status="ok",
        session_id="s1",
    )
    by_file = {p["tool_input"]["file_path"]: p["tool_input"]["new_string"] for _, p in calls}
    assert by_file[written[0]] == "new_a_function()"
    assert by_file[written[1]] == "def only_in_b():\n    pass"


def test_edit_recording_thread_is_not_a_daemon(tmp_path, monkeypatch, calls):
    _built(tmp_path)
    seen = {}

    class Recorder:
        def __init__(self, target, daemon=None):
            seen["daemon"] = daemon
            self._target = target

        def start(self):
            self._target()

    monkeypatch.setattr(threading, "Thread", Recorder)
    plugin.on_post_tool_call(tool_name="write_file", args={"path": "a.py"}, session_id="s1")
    assert seen["daemon"] is False


# --- uninstall, reinstall, and plugins Hermes installed ----------------------


class FakeHermes:
    """Records `hermes plugins <action> neuralmind`; `remove` deletes the plugin as Hermes does."""

    def __init__(self, home: Path, fail: tuple[str, ...] = ()):
        self.home, self.fail, self.actions = home, fail, []

    def __call__(self, command, env, **kwargs):
        action = command[command.index("plugins") + 1]
        self.actions.append(action)
        if action in self.fail:
            return SimpleNamespace(returncode=1)
        if action == "remove":
            shutil.rmtree(self.home / "plugins" / "neuralmind")
        return SimpleNamespace(returncode=0)


def _hermes_home(tmp_path: Path) -> Path:
    home = tmp_path / "hermes"
    home.mkdir()
    (home / "config.yaml").write_text("model: x\n")
    return home


def _with_hermes(monkeypatch, hermes) -> None:
    monkeypatch.setattr(hermes_install.shutil, "which", lambda name: "/bin/hermes")
    monkeypatch.setattr(hermes_install.subprocess, "run", hermes)


def test_uninstall_removes_through_hermes_so_a_reinstall_is_enabled(tmp_path, monkeypatch):
    home = _hermes_home(tmp_path)
    hermes = FakeHermes(home)
    _with_hermes(monkeypatch, hermes)
    hermes_install.install(None, home=home)
    result = hermes_install.uninstall(home)
    assert result["removed"] is True and result["forgotten"] is True
    # `hermes plugins remove` drops the plugin's config entries; `disable` would
    # have left it on plugins.disabled, and a reinstall would have stayed off.
    assert hermes.actions == ["enable", "remove"]
    # A fresh install enables it even if an earlier uninstall left it disabled.
    (home / "config.yaml").write_text("plugins:\n  enabled: []\n  disabled:\n    - neuralmind\n")
    result = hermes_install.install(None, home=home)
    assert result["enabled"] is True and result["disabled_by_user"] is False
    assert hermes.actions[-1] == "enable"


def test_uninstall_disables_when_hermes_cannot_remove(tmp_path, monkeypatch):
    home = _hermes_home(tmp_path)
    hermes_install.install(None, home=home, enable=False)
    hermes = FakeHermes(home, fail=("remove",))
    _with_hermes(monkeypatch, hermes)
    result = hermes_install.uninstall(home)
    assert hermes.actions == ["remove", "disable"]
    assert result["forgotten"] is False and result["disabled"] is True
    assert result["removed"] is True and not (home / "plugins" / "neuralmind").exists()


def test_uninstall_of_a_symlink_disables_it_and_unlinks(tmp_path, monkeypatch):
    # `hermes plugins remove` resolves the link and refuses a target outside
    # its plugins directory, so the link is disabled in Hermes and unlinked here.
    home = _hermes_home(tmp_path)
    (home / "plugins").mkdir()
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    (elsewhere / "keep.txt").write_text("x")
    try:
        (home / "plugins" / "neuralmind").symlink_to(elsewhere, target_is_directory=True)
    except (OSError, NotImplementedError):
        pytest.skip("symlinks unavailable")
    hermes = FakeHermes(home)
    _with_hermes(monkeypatch, hermes)
    result = hermes_install.uninstall(home)
    assert hermes.actions == ["disable"]
    assert result["removed"] is True and result["disabled"] is True
    assert not (home / "plugins" / "neuralmind").exists() and (elsewhere / "keep.txt").exists()


def test_install_into_a_plugin_hermes_installed_writes_only_settings(tmp_path):
    home = tmp_path / "hermes"
    target = home / "plugins" / "neuralmind"
    target.mkdir(parents=True)
    (target / "__init__.py").write_text("# Hermes's pinned copy\n")
    (home / "plugins" / ".install-metadata.json").write_text(
        json.dumps({"neuralmind": {"source": "https://github.com/dfrostar/neuralmind.git"}})
    )
    project = _built(tmp_path / "proj")
    result = hermes_install.install(str(project), home=home, enable=False)
    assert result["managed"] is True
    assert (target / "__init__.py").read_text() == "# Hermes's pinned copy\n"
    assert not (target / "plugin.yaml").exists()
    config = json.loads((target / "config.json").read_text())
    assert config == {"python": sys.executable, "project": str(project.resolve())}


def test_cli_says_turns_get_context_only_once_enabled(tmp_path, capsys, monkeypatch):
    from neuralmind.cli import main

    home = _hermes_home(tmp_path)
    hermes_install.install(None, home=home, enable=False)
    (home / "config.yaml").write_text("plugins:\n  enabled: []\n  disabled:\n    - neuralmind\n")
    _with_hermes(monkeypatch, FakeHermes(home, fail=("enable",)))
    monkeypatch.setattr(
        sys, "argv", ["neuralmind", "install-hermes-plugin", "--hermes-home", str(home)]
    )
    main()
    out = capsys.readouterr().out
    assert "Left disabled" in out
    assert "now gets" not in out and "Once it's enabled, each Hermes turn gets" in out


def test_cli_uninstall_reports_that_hermes_forgot_it(tmp_path, capsys, monkeypatch):
    from neuralmind.cli import main

    home = _hermes_home(tmp_path)
    hermes_install.install(None, home=home, enable=False)
    _with_hermes(monkeypatch, FakeHermes(home))
    monkeypatch.setattr(
        sys,
        "argv",
        ["neuralmind", "install-hermes-plugin", "--uninstall", "--hermes-home", str(home)],
    )
    main()
    out = capsys.readouterr().out
    assert "Removed the NeuralMind plugin" in out and "no longer lists it" in out


# --- the committed manifest Hermes installs from -----------------------------


def _manifest() -> dict:
    import yaml

    return yaml.safe_load((PLUGIN_SOURCE / "plugin.yaml").read_text(encoding="utf-8"))


def test_manifest_declares_exactly_the_hooks_register_wires():
    # Hermes's catalog validation fails an entry whose declared capabilities
    # don't match what register() wires.
    registered = []

    class Ctx:
        def register_hook(self, name, callback):
            registered.append(name)

    plugin.register(Ctx())
    manifest = _manifest()
    assert manifest["name"] == hermes_install.PLUGIN_NAME
    assert sorted(manifest["provides_hooks"]) == sorted(registered)
    assert not manifest.get("provides_tools")


def test_manifest_requires_a_semver_hermes_floor():
    # Hermes skips a plugin whose floor is newer than it, and the catalog
    # rejects a CalVer date there.
    assert re.fullmatch(r">=\d+\.\d+\.\d+", _manifest()["requires_hermes"])


def test_manifest_version_tracks_the_release():
    from neuralmind import __version__

    rel = "neuralmind/hermes_plugin/plugin.yaml"
    lines = (REPO_ROOT / rel).read_text(encoding="utf-8").splitlines()
    (version_line,) = [line for line in lines if line.startswith("version:")]
    # release-please's generic updater bumps only an annotated line.
    assert "x-release-please-version" in version_line
    released = json.loads((REPO_ROOT / ".release-please-manifest.json").read_text())["."]
    assert _manifest()["version"] == __version__ == released
    config = json.loads((REPO_ROOT / "release-please-config.json").read_text())
    assert rel in config["packages"]["."]["extra-files"]


# --- finding NeuralMind --------------------------------------------------------


def test_command_prefers_the_recorded_interpreter_then_path_then_hermes_python(monkeypatch):
    monkeypatch.setattr(plugin, "_python", lambda: "/venv/bin/python")
    monkeypatch.setattr(plugin, "_on_path", lambda name="neuralmind": "/opt/bin/neuralmind")
    assert plugin._command("prompt-submit") == [
        "/venv/bin/python",
        "-m",
        "neuralmind",
        "_hook",
        "prompt-submit",
    ]
    monkeypatch.setattr(plugin, "_python", lambda: None)
    assert plugin._command("prompt-submit") == ["/opt/bin/neuralmind", "_hook", "prompt-submit"]
    monkeypatch.setattr(plugin, "_on_path", lambda name="neuralmind": None)
    assert plugin._command("prompt-submit")[:3] == [sys.executable, "-m", "neuralmind"]


def _script(directory: Path) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    script = directory / ("neuralmind.exe" if sys.platform == "win32" else "neuralmind")
    script.write_text("#!/bin/sh\n")
    script.chmod(0o755)
    return script


def test_path_lookup_never_uses_the_working_directory(tmp_path, monkeypatch):
    # A served repository could carry a `neuralmind` of its own, which
    # shutil.which finds through an empty or relative PATH entry (and on
    # Windows, in the working directory first).
    repo = tmp_path / "repo"
    _script(repo)
    _script(repo / "bin")
    monkeypatch.chdir(repo)
    monkeypatch.setenv("PATH", os.pathsep.join(["", ".", "bin"]))
    assert plugin._on_path() is None
    installed = _script(tmp_path / "venv" / "bin")
    monkeypatch.setenv("PATH", os.pathsep.join([".", str(installed.parent)]))
    assert plugin._on_path() == str(installed)


def test_real_round_trip_through_the_neuralmind_command_on_path(tmp_path, monkeypatch):
    """As in a plugin Hermes installed: no recorded interpreter, `neuralmind` on PATH."""
    bin_dir = Path(sys.executable).parent
    script = bin_dir / ("neuralmind.exe" if sys.platform == "win32" else "neuralmind")
    if not script.is_file():
        pytest.skip("no neuralmind console script next to this interpreter")
    _built(tmp_path)
    monkeypatch.setattr(plugin, "_python", lambda: None)
    monkeypatch.setenv("PATH", str(bin_dir))
    assert plugin._command("prompt-submit")[0] == str(script)
    for var in ("NEURALMIND_SYNAPSE_INJECT", "NEURALMIND_SYNAPSE_EXPORT"):
        monkeypatch.setenv(var, "0")
    monkeypatch.setenv(plugin.TIMEOUT_ENV, "60")
    plugin.on_pre_llm_call(session_id="h1", user_message="add retry logic", is_first_turn=True)
    second = plugin.on_pre_llm_call(session_id="h2", user_message="go on", is_first_turn=True)
    assert second is not None and '"add retry logic"' in second["context"]


# --- telling the user when NeuralMind can't run -------------------------------


def _plugin_warnings(caplog) -> list[str]:
    return [r.getMessage() for r in caplog.records if r.name == plugin.logger.name]


def test_neuralmind_that_cannot_be_found_is_logged_once(monkeypatch, caplog):
    monkeypatch.setattr(plugin, "_command", lambda action: ["/nonexistent/neuralmind"])
    with caplog.at_level(logging.WARNING, logger=plugin.logger.name):
        assert plugin._run("prompt-submit", {}) == ""
        assert plugin._run("session-start", {}) == ""
    (message,) = _plugin_warnings(caplog)
    assert "/nonexistent/neuralmind" in message and "install-hermes-plugin" in message


def test_neuralmind_that_exits_with_an_error_is_logged_with_it(monkeypatch, caplog):
    failing = [sys.executable, "-c", "import sys; sys.exit('No module named neuralmind')"]
    monkeypatch.setattr(plugin, "_command", lambda action: failing)
    with caplog.at_level(logging.WARNING, logger=plugin.logger.name):
        assert plugin._run("prompt-submit", {}) == ""
    (message,) = _plugin_warnings(caplog)
    assert "No module named neuralmind" in message and "install-hermes-plugin" in message


def test_a_timeout_is_logged_with_the_setting_to_raise(monkeypatch, caplog):
    slow = [sys.executable, "-c", "import time; time.sleep(30)"]
    monkeypatch.setattr(plugin, "_command", lambda action: slow)
    monkeypatch.setenv(plugin.TIMEOUT_ENV, "0.5")
    with caplog.at_level(logging.WARNING, logger=plugin.logger.name):
        assert plugin._run("prompt-submit", {}) == ""
    (message,) = _plugin_warnings(caplog)
    assert "took longer than 0.5s" in message and plugin.TIMEOUT_ENV in message


def _reports(version: str) -> list[str]:
    # `<prefix> --version`: the -c script ignores the extra argument.
    return [sys.executable, "-c", f"print('neuralmind {version}')"]


def test_a_neuralmind_too_old_for_the_recap_is_logged(caplog):
    with caplog.at_level(logging.WARNING, logger=plugin.logger.name):
        plugin._check_version(_reports("4.3.5"))
        plugin._check_version(_reports("4.9.0"))
        plugin._check_version(_reports("5.0.1"))
    (message,) = _plugin_warnings(caplog)
    assert "NeuralMind 4.3.5" in message and "no session recap" in message


def test_the_version_is_checked_once_per_process_in_the_background(monkeypatch):
    started = []

    class Recorder:
        def __init__(self, target, args=(), daemon=None):
            started.append((target, args, daemon))

        def start(self):
            pass

    monkeypatch.setattr(plugin, "_version_checked", False)
    monkeypatch.setattr(threading, "Thread", Recorder)
    monkeypatch.setattr(plugin, "_command", lambda action: ["/opt/bin/neuralmind", "_hook", action])
    plugin._run("session-start", {})
    plugin._run("prompt-submit", {})
    assert started == [(plugin._check_version, (["/opt/bin/neuralmind"],), True)]
