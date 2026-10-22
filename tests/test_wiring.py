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
    monkeypatch.delenv("HERMES_HOME", raising=False)
    monkeypatch.delenv("NEURALMIND_NO_DAEMON", raising=False)
    monkeypatch.setenv("NEURALMIND_DAEMON_HOME", str(tmp_path / "daemon"))
    return home


@pytest.fixture
def repo(tmp_path):
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
    assert partial.fix == f"neuralmind init-hook {repo}"

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
    assert "TERMINAL_CWD" in item.detail


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
    assert steps[0].endswith("neuralmind init-hook '../my proj'")
    assert steps[-1] == "neuralmind install-hooks '../my proj'"


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
