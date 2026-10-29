"""Tests for neuralmind/wiring.py: is anything calling NeuralMind for a project?

Every probe runs against a fake HOME, Hermes home and daemon discovery file, so
nothing here reads the developer's real ~/.hermes, ~/.claude.json or daemon.
No Hermes code runs: the plugin's state is read from files.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
from pathlib import Path

import pytest

from neuralmind import __version__, wiring


@pytest.fixture
def home(tmp_path, monkeypatch):
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("USERPROFILE", str(home))
    # Windows keeps Hermes's default home under %LOCALAPPDATA% and Claude
    # Desktop's and VS Code's settings under %APPDATA%: point all three into
    # the fake home, so the runner's own apps stay out of the test.
    monkeypatch.setenv("HERMES_HOME", str(home / ".hermes"))
    monkeypatch.setenv("APPDATA", str(home / "AppData" / "Roaming"))
    monkeypatch.setenv("LOCALAPPDATA", str(home / "AppData" / "Local"))
    monkeypatch.delenv("NEURALMIND_NO_DAEMON", raising=False)
    monkeypatch.setenv("NEURALMIND_DAEMON_HOME", str(tmp_path / "daemon"))
    return home


@pytest.fixture
def repo(tmp_path, monkeypatch):
    # The machine's own git config (a global core.hooksPath, say) stays out.
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", os.devnull)
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")
    project = tmp_path / "proj"
    project.mkdir()
    subprocess.run(["git", "init", "-q", str(project)], check=True)
    return project


def _hermes_home(home: Path, config: str = "model: x\n") -> Path:
    hermes = home / ".hermes"
    hermes.mkdir(parents=True, exist_ok=True)
    (hermes / "config.yaml").write_text(config, encoding="utf-8")
    return hermes


def _plugin(hermes: Path, version: str = __version__, **config) -> Path:
    target = hermes / "plugins" / "neuralmind"
    target.mkdir(parents=True)
    (target / "plugin.yaml").write_text(
        f'name: neuralmind\nversion: "{version}" # x-release-please-version\n',
        encoding="utf-8",
    )
    (target / "config.json").write_text(json.dumps(config), encoding="utf-8")
    return target


# --------------------------------------------------------------------------- #
# Daemon
# --------------------------------------------------------------------------- #
def test_daemon_not_running(home):
    item = wiring.daemon_item()
    assert item.wired is False and item.fix == "neuralmind daemon start"
    assert "not running" in item.detail


def test_daemon_with_a_dead_pid_is_not_running(home, tmp_path, monkeypatch):
    from neuralmind import daemon

    daemon.write_discovery({"host": "127.0.0.1", "port": 1, "token": "t", "pid": 4242})
    monkeypatch.setattr(daemon, "_pid_alive", lambda pid: False)
    item = wiring.daemon_item()
    assert item.wired is False and "pid 4242" in item.detail
    # Read-only: a stale discovery file is left for `daemon start` to replace.
    assert daemon.read_discovery() is not None


def test_daemon_alive_but_silent_needs_a_restart(home, monkeypatch):
    import os

    from neuralmind import daemon

    daemon.write_discovery({"host": "127.0.0.1", "port": 9, "token": "t", "pid": os.getpid()})
    item = wiring.daemon_item(timeout=0.2)
    assert item.wired is False and item.fix == "neuralmind daemon restart"
    assert "doesn't answer on 127.0.0.1:9" in item.detail


@pytest.mark.parametrize("version, outdated", [(__version__, False), ("0.0.1", True)])
def test_daemon_running(home, monkeypatch, version, outdated):
    import os

    from neuralmind import daemon, daemon_client

    daemon.write_discovery({"host": "127.0.0.1", "port": 8787, "token": "t", "pid": os.getpid()})
    monkeypatch.setattr(
        daemon_client.DaemonClient,
        "health",
        lambda self, timeout=2.0: {"pid": os.getpid(), "version": version},
    )
    item = wiring.daemon_item()
    assert item.wired is True and item.outdated is outdated
    assert "running on 127.0.0.1:8787" in item.detail
    assert item.needs_fix is outdated
    if outdated:
        assert item.fix == "neuralmind daemon restart"


def test_daemon_switched_off(home, monkeypatch):
    monkeypatch.setenv("NEURALMIND_NO_DAEMON", "1")
    item = wiring.daemon_item()
    assert item.wired is None and not item.needs_fix


# --------------------------------------------------------------------------- #
# Git hooks
# --------------------------------------------------------------------------- #
def _init_hook(project: Path, **flags) -> None:
    from neuralmind import cli

    args = argparse.Namespace(project_path=str(project), sync=False, strict=False, no_drift=False)
    for key, value in flags.items():
        setattr(args, key, value)
    cli.cmd_init_hook(args)


def test_git_hooks_none_partial_full(repo, capsys):
    none = wiring.git_hooks_item(repo, ".")
    assert none.wired is False and none.detail.startswith("none:")
    assert none.fix == "neuralmind init-hook ."

    _init_hook(repo, no_drift=True)
    partial = wiring.git_hooks_item(repo)
    assert partial.wired is False and partial.detail.startswith("partial:")
    assert "drift guard is missing" in partial.detail
    assert partial.fix == f"neuralmind init-hook {wiring.shell_arg(str(repo))}"

    _init_hook(repo)
    full = wiring.git_hooks_item(repo)
    assert full.wired is True and full.detail.startswith("full:")


def test_git_hooks_of_another_project_in_the_repo_dont_count(repo, capsys):
    sub = repo / "pkg"
    sub.mkdir()
    _init_hook(sub)
    item = wiring.git_hooks_item(repo)
    assert item.wired is False
    assert "serving another project in this repository" in item.detail
    assert wiring.git_hooks_item(sub).wired is True


def test_git_hooks_skipped_by_core_hooks_path(repo, capsys):
    # A false "full": git runs core.hooksPath's hooks, never .git/hooks.
    _init_hook(repo)
    subprocess.run(["git", "-C", str(repo), "config", "core.hooksPath", ".husky"], check=True)
    item = wiring.git_hooks_item(repo)
    assert item.wired is False and "core.hooksPath" in item.detail
    assert item.fix == ""  # nothing of ours to run: the user's hook setup decides


@pytest.mark.skipif(os.name == "nt", reason="POSIX executable bit")
def test_a_hook_git_cant_execute_isnt_wired(repo, capsys):
    # git skips a hook without its executable bit, block or no block.
    _init_hook(repo)
    hooks = repo / ".git" / "hooks"
    (hooks / "post-merge").chmod(0o644)
    item = wiring.git_hooks_item(repo, ".")
    assert item.wired is False and item.detail.startswith("partial:")
    assert "post-merge not executable, so git skips them" in item.detail
    assert item.fix == "neuralmind init-hook ."
    _init_hook(repo)  # the fix: init-hook sets the bit again
    assert wiring.git_hooks_item(repo).wired is True


def test_git_hooks_outside_git_dont_apply(tmp_path):
    plain = tmp_path / "plain"
    plain.mkdir()
    item = wiring.git_hooks_item(plain)
    assert item.wired is None and not item.needs_fix


def test_git_hooks_probe_creates_nothing(tmp_path):
    # A linked worktree's hooks dir is resolved through git; the probe must not
    # create it the way init-hook does.
    main = tmp_path / "main"
    subprocess.run(["git", "init", "-q", str(main)], check=True)
    hooks = main / ".git" / "hooks"
    if hooks.exists():
        for f in hooks.iterdir():
            f.unlink()
        hooks.rmdir()
    sub = main / "sub"
    sub.mkdir()
    wiring.git_hooks_item(sub)
    assert not hooks.exists()


# --------------------------------------------------------------------------- #
# Hermes plugin
# --------------------------------------------------------------------------- #
def test_no_hermes_means_not_applicable(home, tmp_path):
    item = wiring.hermes_plugin_item(tmp_path)
    assert item.wired is None and not item.needs_fix


def test_hermes_without_the_plugin(home, tmp_path):
    _hermes_home(home)
    item = wiring.hermes_plugin_item(tmp_path)
    assert item.wired is False and item.fix == "neuralmind install-hermes-plugin"


@pytest.mark.parametrize(
    "plugins, fragment",
    [
        ("", "not on Hermes's plugins.enabled list"),
        (
            "plugins:\n  enabled: [neuralmind]\n  disabled: [neuralmind]\n",
            "plugins.disabled",
        ),
    ],
)
def test_hermes_plugin_installed_but_off(home, tmp_path, plugins, fragment):
    hermes = _hermes_home(home, "model: x\n" + plugins)
    _plugin(hermes)
    item = wiring.hermes_plugin_item(tmp_path)
    assert item.wired is False and fragment in item.detail
    assert item.fix == "hermes plugins enable neuralmind"


def test_hermes_plugin_enabled(home, tmp_path):
    hermes = _hermes_home(home, "plugins:\n  enabled:\n    - neuralmind\n")
    _plugin(hermes)
    item = wiring.hermes_plugin_item(tmp_path)
    assert item.wired is True and item.host and not item.needs_fix
    assert "serves the directory Hermes works in for each session" in item.detail


def test_hermes_plugin_pinned_here_or_elsewhere(home, tmp_path):
    hermes = _hermes_home(home, "plugins:\n  enabled: [neuralmind]\n")
    _plugin(hermes, project=str(tmp_path / "other"))
    elsewhere = wiring.hermes_plugin_item(tmp_path)
    assert elsewhere.wired is False and "pinned to" in elsewhere.detail
    assert elsewhere.fix == "neuralmind install-hermes-plugin --unpin"
    assert elsewhere.suggest is False  # build never offers to undo a pin

    (hermes / "plugins" / "neuralmind" / "config.json").write_text(
        json.dumps({"project": str(tmp_path)}), encoding="utf-8"
    )
    here = wiring.hermes_plugin_item(tmp_path)
    assert here.wired is True and "pinned to this project" in here.detail


def test_hermes_plugin_from_an_older_release_is_outdated(home, tmp_path):
    hermes = _hermes_home(home, "plugins:\n  enabled: [neuralmind]\n")
    _plugin(hermes, version="4.15.0")
    item = wiring.hermes_plugin_item(tmp_path)
    # Still wired (the shim runs the installed NeuralMind), but worth a re-run.
    assert item.wired is True and item.outdated and item.needs_fix
    assert "v4.15.0" in item.detail and item.fix == "neuralmind install-hermes-plugin"


def test_hermes_plugin_hermes_installed_is_updated_by_hermes(home, tmp_path):
    hermes = _hermes_home(home, "plugins:\n  enabled: [neuralmind]\n")
    _plugin(hermes, version="4.15.0")
    (hermes / "plugins" / ".install-metadata.json").write_text('{"neuralmind": {}}')
    assert wiring.hermes_plugin_item(tmp_path).fix == "hermes plugins update neuralmind"


# --------------------------------------------------------------------------- #
# MCP registrations
# --------------------------------------------------------------------------- #
def test_no_mcp_client_found_is_one_manual_warning(home, tmp_path):
    items = wiring.mcp_items(tmp_path)
    assert [i.name for i in items] == ["MCP registration"]
    assert items[0].wired is False and items[0].fix == "neuralmind install-mcp --print"


def test_mcp_registered_in_the_project(home, tmp_path):
    (tmp_path / ".mcp.json").write_text(
        json.dumps({"mcpServers": {"nm": {"command": "/venv/bin/neuralmind-mcp"}}})
    )
    (item,) = wiring.mcp_items(tmp_path)
    assert item.name == "MCP registration (claude-code)" and item.wired is True


def test_mcp_registered_with_claude_mcp_add(home, tmp_path):
    entry = {"command": "neuralmind-mcp", "args": []}
    (home / ".claude.json").write_text(
        json.dumps({"projects": {str(tmp_path.resolve()): {"mcpServers": {"neuralmind": entry}}}})
    )
    (tmp_path / ".mcp.json").write_text("{}")  # Claude Code detected, entry elsewhere
    (item,) = wiring.mcp_items(tmp_path)
    assert item.wired is True and "local scope, ~/.claude.json" in item.detail


def test_mcp_detected_client_without_the_entry(home, tmp_path):
    _hermes_home(home)
    items = {i.name: i for i in wiring.mcp_items(tmp_path)}
    hermes = items["MCP registration (hermes)"]
    assert hermes.wired is False and hermes.fix == "neuralmind install-mcp --client hermes"


@pytest.mark.parametrize("key", ["neuralmind", "nm"])
def test_mcp_disabled_in_hermes(home, tmp_path, key):
    _hermes_home(
        home,
        f"mcp_servers:\n  {key}:\n    command: neuralmind-mcp\n    enabled: false\n",
    )
    hermes = {i.name: i for i in wiring.mcp_items(tmp_path)}["MCP registration (hermes)"]
    assert hermes.wired is False and "disabled" in hermes.detail and hermes.suggest is False
    # The fix names the entry that is actually there.
    assert hermes.fix == f"hermes config set mcp_servers.{key}.enabled true"


# --------------------------------------------------------------------------- #
# Summary state and build's next steps
# --------------------------------------------------------------------------- #
def _item(wired, host=False, outdated=False):
    return wiring.WiringItem("x", wired, "", host=host, outdated=outdated)


def test_state():
    unwired_host = [_item(True), _item(False, host=True)]
    assert wiring.state(unwired_host, claude_code_hooks=False) == wiring.INERT
    # Claude Code's hooks are a host too.
    assert wiring.state(unwired_host, claude_code_hooks=True) == wiring.PARTIAL
    assert wiring.state([_item(True, host=True), _item(None)], False) == wiring.WIRED
    assert wiring.state([_item(True, host=True, outdated=True)], False) == wiring.PARTIAL


def test_next_steps_on_a_fresh_machine_with_hermes(home, repo):
    _hermes_home(home)
    assert wiring.next_steps(repo, ".") == [
        "neuralmind daemon start && neuralmind init-hook .",
        "neuralmind install-hermes-plugin && neuralmind install-mcp --client hermes",
    ]


def test_next_steps_offer_hermes_mcp_only_where_it_can_be_written(home, repo):
    # A Hermes home with .env but no config.yaml: the plugin can be installed,
    # but install-mcp --client hermes has no file to add the entry to.
    (home / ".hermes").mkdir()
    (home / ".hermes" / ".env").write_text("X=1\n")
    assert wiring.next_steps(repo, ".")[-1] == "neuralmind install-hermes-plugin"


def test_next_steps_without_hermes_offers_one_agent_host(home, repo):
    # No MCP client to write to, so `install-mcp --all` would find none: the
    # entry to paste is the step that does something.
    assert wiring.next_steps(repo, ".")[-1] == "neuralmind install-mcp --print"
    # A client that's set up but lacks the entry: --all writes it.
    (repo / ".cursor").mkdir()
    (repo / ".cursor" / "mcp.json").write_text("{}")
    assert wiring.next_steps(repo, "proj")[-1] == "neuralmind install-mcp proj --all"
    (home / ".claude").mkdir()
    assert wiring.next_steps(repo, ".")[-1] == "neuralmind install-hooks ."


def test_next_steps_name_the_project_that_was_built(home, repo):
    # Pasted from the directory build ran in, the commands still wire `repo`.
    (home / ".claude").mkdir()
    steps = wiring.next_steps(repo, "../my proj")
    arg = wiring.shell_arg("../my proj")
    assert steps[0].endswith(f"neuralmind init-hook {arg}")
    assert steps[-1] == f"neuralmind install-hooks {arg}"


def test_next_steps_say_nothing_once_wired(home, repo, monkeypatch, capsys):
    _init_hook(repo)
    hermes = _hermes_home(
        home,
        "plugins:\n  enabled: [neuralmind]\nmcp_servers:\n  neuralmind:\n    command: neuralmind-mcp\n",
    )
    _plugin(hermes)
    monkeypatch.setenv("NEURALMIND_NO_DAEMON", "1")
    assert wiring.next_steps(repo, ".") == []


def test_next_steps_never_offer_to_undo_a_pin(home, repo, monkeypatch, capsys):
    _init_hook(repo)
    hermes = _hermes_home(
        home,
        "plugins:\n  enabled: [neuralmind]\nmcp_servers:\n  neuralmind:\n    command: neuralmind-mcp\n",
    )
    _plugin(hermes, project=str(repo.parent / "other"))
    monkeypatch.setenv("NEURALMIND_NO_DAEMON", "1")
    assert wiring.next_steps(repo, ".") == []


def test_build_prints_at_most_three_lines(home, repo, capsys):
    from neuralmind.cli import _print_next_steps

    _hermes_home(home)
    _print_next_steps(str(repo))
    lines = capsys.readouterr().out.strip("\n").splitlines()
    assert len(lines) == 3
    assert lines[1].strip().startswith("neuralmind daemon start")
    assert lines[2].strip().endswith("neuralmind install-mcp --client hermes")


def test_build_keeps_the_watch_hint_when_there_is_room(home, repo, monkeypatch, capsys):
    from neuralmind.cli import _print_next_steps

    _init_hook(repo)
    monkeypatch.setenv("NEURALMIND_NO_DAEMON", "1")
    monkeypatch.chdir(repo)
    entry = {"mcpServers": {"neuralmind": {"command": "neuralmind-mcp"}}}
    (repo / ".mcp.json").write_text(json.dumps(entry))
    capsys.readouterr()
    _print_next_steps(".")
    out = capsys.readouterr().out
    assert "Next, wire it in" not in out
    assert "neuralmind watch . --reindex" in out


# --------------------------------------------------------------------------- #
# Review fixes
# --------------------------------------------------------------------------- #
def test_shell_arg_quotes_for_the_platform(monkeypatch):
    monkeypatch.setattr(wiring, "_WINDOWS", False)
    assert wiring.shell_arg("my proj") == "'my proj'"
    monkeypatch.setattr(wiring, "_WINDOWS", True)
    # cmd.exe and PowerShell would keep single quotes as part of the path.
    assert wiring.shell_arg(r".\proj") == r".\proj"
    assert wiring.shell_arg(r"C:\my proj") == r'"C:\my proj"'


def test_another_projects_hooks_are_never_offered_for_taking_over(repo, capsys):
    sub = repo / "pkg"
    sub.mkdir()
    _init_hook(sub)
    item = wiring.git_hooks_item(repo, ".")
    assert item.wired is False and item.fix and item.suggest is False


def test_a_client_doctor_cant_read_keeps_the_verdict_off_inert(home, tmp_path):
    # VS Code accepts comments in settings.json; doctor's JSON reader doesn't,
    # so it can't tell whether NeuralMind is registered there.
    from neuralmind import mcp_install

    settings = mcp_install.config_path("vscode", tmp_path)  # under the fake home
    settings.parent.mkdir(parents=True)
    settings.write_text(
        '{\n  // mine\n  "mcp.servers": {"neuralmind": {"command": "neuralmind-mcp"}}\n}\n'
    )
    items = wiring.mcp_items(tmp_path)
    vscode = {i.name: i for i in items}["MCP registration (vscode)"]
    assert vscode.wired is None and "can't tell" in vscode.detail
    assert wiring.state(items, claude_code_hooks=False) == wiring.PARTIAL


def test_one_failing_probe_leaves_the_others_standing(home, repo, monkeypatch):
    def broken():
        raise AttributeError("'list' object has no attribute 'get'")

    monkeypatch.setattr(wiring, "daemon_item", broken)
    items = wiring.collect(repo, ".")
    assert items[0].name == "Daemon" and items[0].wired is None
    assert "could not check (AttributeError" in items[0].detail
    assert [i.name for i in items[1:3]] == ["Git hooks", "Hermes plugin"]
    assert wiring.next_steps(repo, ".")[0] == "neuralmind init-hook ."


def test_a_discovery_file_that_isnt_an_object(home):
    from neuralmind import daemon

    daemon.discovery_path().parent.mkdir(parents=True, exist_ok=True)
    daemon.discovery_path().write_text("[1]")
    item = wiring.daemon_item()
    assert item.wired is False and "delete it" in item.detail and item.fix == ""


def test_a_plugin_yaml_that_isnt_utf8(home, tmp_path):
    hermes = _hermes_home(home, "plugins:\n  enabled: [neuralmind]\n")
    target = _plugin(hermes)
    (target / "plugin.yaml").write_bytes(b"name: neuralmind\nversion: \xff\n")
    assert wiring.hermes_plugin_item(tmp_path).wired is True


def test_an_outdated_plugin_with_unreadable_install_records(home, tmp_path):
    # install-hermes-plugin leaves the code alone then, so it isn't the fix.
    hermes = _hermes_home(home, "plugins:\n  enabled: [neuralmind]\n")
    _plugin(hermes, version="4.15.0")
    (hermes / "plugins" / ".install-metadata.json").write_text("{not json")
    item = wiring.hermes_plugin_item(tmp_path)
    assert item.outdated and item.fix == "" and item.suggest is False
    assert ".install-metadata.json can't be read" in item.detail


@pytest.mark.skipif(os.name == "nt", reason="symlinks need privileges on Windows")
def test_a_symlinked_hermes_config_gets_the_entry_to_paste(home, tmp_path):
    hermes = home / ".hermes"
    hermes.mkdir()
    managed = tmp_path / "managed.yaml"
    managed.write_text("model: x\n")
    (hermes / "config.yaml").symlink_to(managed)
    item = {i.name: i for i in wiring.mcp_items(tmp_path)}["MCP registration (hermes)"]
    assert item.fix == "neuralmind install-mcp --client hermes --print"
    assert item.suggest is False and "symlink" in item.detail


def test_a_disabled_entry_hermes_config_set_cant_address(home, tmp_path):
    _hermes_home(
        home, "mcp_servers:\n  nm.local:\n    command: neuralmind-mcp\n    enabled: false\n"
    )
    item = {i.name: i for i in wiring.mcp_items(tmp_path)}["MCP registration (hermes)"]
    assert item.wired is False and item.fix == ""
    assert "set enabled: true on that entry" in item.detail


def test_claude_code_hooks_in_settings_local_count(home, tmp_path):
    local = tmp_path / ".claude" / "settings.local.json"
    local.parent.mkdir()
    block = {"hooks": [{"type": "command", "command": "neuralmind _hook prompt-submit"}]}
    local.write_text(json.dumps({"hooks": {"UserPromptSubmit": [block]}}))
    assert wiring.claude_code_hook_scopes(tmp_path) == ["project local"]


def test_cursor_registered_user_wide(home, tmp_path):
    (home / ".cursor").mkdir()
    entry = {"mcpServers": {"neuralmind": {"command": "neuralmind-mcp"}}}
    (home / ".cursor" / "mcp.json").write_text(json.dumps(entry))
    cursor = {i.name: i for i in wiring.mcp_items(tmp_path)}["MCP registration (cursor)"]
    assert cursor.wired is True and "~/.cursor/mcp.json" in cursor.detail
