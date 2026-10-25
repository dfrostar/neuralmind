# SPDX-License-Identifier: MIT
"""wiring.py — is anything actually calling NeuralMind for this project?

A built index that no agent queries is installed but inert: the graph and the
vectors are fine, so every health check passes, and nothing uses them. A field
deployment sat that way for eleven days with two logged queries. The pieces
that connect a built project to its use are:

- the daemon, which keeps the index warm for CLI queries;
- the Git hooks ``neuralmind init-hook`` installs, which rebuild the index
  after commits, merges, branch switches and rebases, and guard commits for
  drift;
- the agent hosts: Claude Code's hooks, the Hermes-Agent plugin, and the MCP
  server registered in a client's config.

Each probe here is read-only and never raises: one it can't run reports what
it couldn't see. ``neuralmind doctor`` shows them as its Wiring section, and
``neuralmind build`` prints the commands for the ones still missing.
"""

from __future__ import annotations

import json
import os
import re
import shlex
import shutil
import subprocess  # nosec B404 - runs git, by absolute path, with a fixed argument list
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

# Hook files ``neuralmind init-hook`` writes a managed block into: the four
# that rebuild the index, then the pre-commit drift guard.
REBUILD_HOOKS = ("post-commit", "post-merge", "post-checkout", "post-rewrite")
GIT_HOOKS = (*REBUILD_HOOKS, "pre-commit")
_BLOCK_START = "# neuralmind-hook-start"
_BLOCK_END = "# neuralmind-hook-end"
# How a managed block names its project: the rebuild hooks test the built
# marker, the drift guard passes the path to `drift`.
_REBUILD_TARGET = re.compile(r"\[ -f (.+?)/\.neuralmind/build_status\.json \]")
_DRIFT_TARGET = re.compile(r'"\$_nm_bin" drift (.+?) --staged')
_PLUGIN_VERSION = re.compile(r'^version:\s*["\']?([^"\'\s#]+)', re.MULTILINE)
# A Hermes config key `hermes config set` can address as one dotted segment.
_PLAIN_KEY = re.compile(r"^[A-Za-z0-9_-]+$")
# Whether pasted commands are for cmd.exe / PowerShell (tests flip it).
_WINDOWS = os.name == "nt"


@dataclass
class WiringItem:
    """One piece of wiring.

    ``wired`` is True or False, or None when it doesn't apply here (no Hermes
    on this machine, a project outside Git). ``fix`` is the one command that
    wires it. ``host`` marks an item through which an agent calls NeuralMind.
    ``outdated`` marks a piece that is wired but runs old code (a daemon or
    plugin copy from before an upgrade): it still works, and ``fix`` updates
    it. ``suggest`` is False for a fix that undoes a deliberate choice
    (another project's pin, another project's Git hooks) or can't apply as
    printed, which ``build`` doesn't offer unasked.
    """

    name: str
    wired: bool | None
    detail: str
    fix: str = ""
    host: bool = False
    suggest: bool = True
    outdated: bool = False

    @property
    def needs_fix(self) -> bool:
        return self.wired is False or self.outdated


def shell_arg(value: str) -> str:
    """``value`` quoted for pasting into this platform's shell.

    POSIX shells take single quotes; cmd.exe and PowerShell would pass them on
    literally, so Windows gets the double quotes ``list2cmdline`` adds when
    they're needed (a path with a backslash and no space needs none).
    """
    return subprocess.list2cmdline([value]) if _WINDOWS else shlex.quote(value)


def _arg(project: Path, project_arg: str | None) -> str:
    """The project as a command argument: what the user typed, else the path."""
    return shell_arg(project_arg if project_arg else str(project))


# --------------------------------------------------------------------------- #
# Daemon
# --------------------------------------------------------------------------- #
def daemon_item(timeout: float = 1.0) -> WiringItem:
    """Is the daemon up, answering, and running the installed version?"""
    name = "Daemon"
    if os.environ.get("NEURALMIND_NO_DAEMON") == "1":
        return WiringItem(name, None, "off: NEURALMIND_NO_DAEMON=1 keeps every CLI call direct")
    try:
        from . import __version__
        from .daemon import DEFAULT_PORT, _pid_alive, read_discovery
        from .daemon_client import DaemonClient, DaemonUnavailableError

        info = read_discovery()
    except Exception as exc:  # pragma: no cover - diagnostic must never raise
        return WiringItem(name, None, f"could not check the daemon ({exc})")
    start = "neuralmind daemon start"
    cold = "not running: CLI queries load the index from cold on every call"
    if not info:
        return WiringItem(name, False, cold, fix=start)
    if not isinstance(info, dict):
        # `daemon start` reads this file too and can't use it: say so.
        return WiringItem(
            name,
            False,
            f"{cold}; its discovery file isn't one the daemon wrote: delete it, then: {start}",
        )
    host = info.get("host", "127.0.0.1")
    port = info.get("port", DEFAULT_PORT)
    pid = info.get("pid")
    if isinstance(pid, int) and pid > 0 and not _pid_alive(pid):
        return WiringItem(
            name, False, f"{cold} (pid {pid} in its discovery file has exited)", start
        )
    try:
        health = DaemonClient(info).health(timeout=timeout)
    except (DaemonUnavailableError, KeyError, TypeError, ValueError):
        return WiringItem(
            name,
            False,
            f"pid {pid} is alive but doesn't answer on {host}:{port}",
            fix="neuralmind daemon restart",
        )
    running = f"running on {host}:{port} (pid {health.get('pid', pid)}"
    version = health.get("version")
    if version and version != __version__:
        return WiringItem(
            name,
            True,
            f"{running}) runs v{version}, but v{__version__} is installed",
            fix="neuralmind daemon restart",
            outdated=True,
        )
    return WiringItem(name, True, f"{running}, v{version or '?'})")


# --------------------------------------------------------------------------- #
# Git hooks
# --------------------------------------------------------------------------- #
def _hooks_location(project: Path) -> tuple[Path | None, Path | None, Path | None]:
    """``(hooks dir init-hook writes, repository root, hooks dir git runs)``.

    The first two are the CLI's ``_git_hooks_location``, without creating the
    directory; the third honours ``core.hooksPath``. One ``git rev-parse``, by
    git's absolute path (not one a changed PATH could swap), with a fixed
    argument list and no shell. All None outside a repository.
    """
    direct = project / ".git" / "hooks"
    git = shutil.which("git")
    lines: list[str] = []
    if git is not None:
        command = [git, "-C", str(project), "rev-parse", "--show-toplevel"]
        command += ["--git-common-dir", "--git-path", "hooks"]
        try:
            out = subprocess.run(  # nosec B603 - git by absolute path, fixed arguments, no shell
                command, capture_output=True, text=True, timeout=10, check=False
            )
            lines = out.stdout.strip().splitlines() if out.returncode == 0 else []
        except (OSError, subprocess.SubprocessError):
            lines = []
    if len(lines) != 3:
        # No git to ask: init-hook still writes to a .git/hooks it finds.
        return (direct, project, None) if direct.is_dir() else (None, None, None)
    top, common, runs = (
        Path(os.path.normpath(line if os.path.isabs(line) else project / line)) for line in lines
    )
    if direct.is_dir():
        return direct, project, runs
    return common / "hooks", top, runs


def _managed_block(hook_file: Path) -> str | None:
    try:
        text = hook_file.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None
    if _BLOCK_START not in text or _BLOCK_END not in text:
        return None
    return text.partition(_BLOCK_START)[2].partition(_BLOCK_END)[0]


def git_hooks_item(project: Path, project_arg: str | None = None) -> WiringItem:
    """none / partial / full: which of init-hook's five hooks serve this project."""
    name = "Git hooks"
    try:
        hooks_dir, repo_root, runs = _hooks_location(project)
    except Exception as exc:  # pragma: no cover - diagnostic must never raise
        return WiringItem(name, None, f"could not check ({exc})")
    if hooks_dir is None or repo_root is None:
        return WiringItem(
            name,
            None,
            "not a Git repository: rebuild with `neuralmind build` after changes",
        )
    if runs is not None and os.path.realpath(runs) != os.path.realpath(hooks_dir):
        # init-hook writes the repository's own hooks directory; with
        # core.hooksPath set (husky, a shared hooks repo) git never runs it.
        return WiringItem(
            name,
            False,
            f"git runs the hooks in {runs} (core.hooksPath), but init-hook writes "
            f"{hooks_dir}, so NeuralMind's rebuilds never run there; add its blocks to the "
            "hooks git runs, or unset core.hooksPath",
        )
    rel = os.path.relpath(os.path.realpath(project), os.path.realpath(repo_root))
    target = "." if rel == "." else shlex.quote(rel.replace(os.sep, "/"))
    present: list[str] = []
    elsewhere: list[str] = []
    skipped: list[str] = []
    for hook in GIT_HOOKS:
        hook_file = hooks_dir / hook
        block = _managed_block(hook_file)
        if block is None:
            continue
        pattern = _DRIFT_TARGET if hook == "pre-commit" else _REBUILD_TARGET
        found = pattern.search(block)
        if found is not None and found.group(1) != target:
            elsewhere.append(f"{hook} ({found.group(1)})")
        elif not os.access(hook_file, os.X_OK):
            # git skips a hook it can't execute; init-hook sets the bit again.
            skipped.append(hook)
        else:
            present.append(hook)
    fix = f"neuralmind init-hook {_arg(project, project_arg)}"
    missing = [h for h in GIT_HOOKS if h not in present]
    if not missing:
        return WiringItem(
            name,
            True,
            "full: commits, merges, branch switches and rebases rebuild the index; "
            "pre-commit runs the drift guard",
        )
    note = ""
    if skipped:
        note += f"; {', '.join(skipped)} not executable, so git skips them"
    if elsewhere:
        # One managed block per hook file: another project in this repository
        # took it over.
        note += (
            f"; serving another project in this repository: {', '.join(elsewhere)} "
            "(init-hook here takes them over)"
        )
    # Taking over another project's hooks is a choice for doctor's reader,
    # not a step `build` offers.
    suggest = not elsewhere
    if not present:
        return WiringItem(
            name,
            False,
            "none: the index goes stale after commits, pulls and branch switches until "
            f"the next manual build{note}",
            fix=fix,
            suggest=suggest,
        )
    if missing == ["pre-commit"] and not elsewhere and not skipped:
        what = "the pre-commit drift guard is missing (an install with --no-drift)"
    else:
        what = f"missing {', '.join(missing)}"
    return WiringItem(
        name,
        False,
        f"partial: {', '.join(present)} installed; {what}{note}",
        fix=fix,
        suggest=suggest,
    )


# --------------------------------------------------------------------------- #
# Claude Code hooks
# --------------------------------------------------------------------------- #
def _read_json(path: Path) -> object | None:
    """``path`` parsed as JSON; None when it's missing or isn't JSON."""
    try:
        data: object = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return data


def claude_code_hook_scopes(project: Path) -> list[str]:
    """The settings scopes (``project``, ``project local``, ``global``) holding NeuralMind's hooks.

    Raises if :mod:`neuralmind.hooks` can't be imported, so doctor can say it
    couldn't check rather than "not installed".
    """
    from .hooks import _is_neuralmind_block, _settings_path

    project_settings = _settings_path("project", str(project))
    scopes = (
        ("project", project_settings),
        # Claude Code also reads hooks someone moved to the uncommitted file.
        ("project local", project_settings.with_name("settings.local.json")),
        ("global", _settings_path("global")),
    )
    installed = []
    for label, path in scopes:
        data = _read_json(path)
        hooks = data.get("hooks") if isinstance(data, dict) else None
        blocks = [
            block
            for event_blocks in (hooks if isinstance(hooks, dict) else {}).values()
            if isinstance(event_blocks, list)
            for block in event_blocks
        ]
        if any(_is_neuralmind_block(b) for b in blocks):
            installed.append(label)
    return installed


# --------------------------------------------------------------------------- #
# Hermes-Agent plugin
# --------------------------------------------------------------------------- #
def _hermes_config(home: Path) -> dict | None:
    """``<home>/config.yaml`` as a dict; None when absent or unreadable."""
    try:
        import yaml

        data = yaml.safe_load((home / "config.yaml").read_text(encoding="utf-8-sig"))
    except Exception:
        return None
    return data if isinstance(data, dict) else ({} if data is None else None)


def _names(value) -> list[str]:
    return [str(v) for v in value] if isinstance(value, list) else []


def hermes_plugin_item(project: Path, home: Path | None = None) -> WiringItem:
    """not installed / installed / enabled, for the Hermes home plain `hermes` uses."""
    name = "Hermes plugin"
    try:
        from . import __version__
        from .hermes_install import (
            PLUGIN_NAME,
            hermes_home,
            is_hermes_home,
            managed_by_hermes,
        )

        home = home or hermes_home()
    except Exception as exc:  # pragma: no cover - diagnostic must never raise
        return WiringItem(name, None, f"could not check ({exc})")
    where = str(home) + (f" (Hermes profile {home.name})" if home.parent.name == "profiles" else "")
    target = home / "plugins" / PLUGIN_NAME
    installed = (target / "plugin.yaml").is_file()
    if not installed:
        if not is_hermes_home(home):
            return WiringItem(name, None, f"no Hermes home at {where}; skip unless you use Hermes")
        return WiringItem(
            name,
            False,
            f"Hermes is set up at {where}, but the NeuralMind plugin isn't installed",
            fix="neuralmind install-hermes-plugin",
            host=True,
        )
    config = _hermes_config(home)
    plugins = (config or {}).get("plugins")
    plugins = plugins if isinstance(plugins, dict) else {}
    enabled = _names(plugins.get("enabled"))
    disabled = _names(plugins.get("disabled"))
    enable = f"hermes plugins enable {PLUGIN_NAME}"
    if config is None:
        return WiringItem(
            name,
            False,
            f"installed at {target}, but {home / 'config.yaml'} is missing or unreadable, "
            "so Hermes doesn't load it; set Hermes up (run `hermes`), then enable it",
            fix=enable,
            host=True,
        )
    if PLUGIN_NAME in disabled:
        return WiringItem(
            name,
            False,
            f"installed at {target}, but on Hermes's plugins.disabled list",
            enable,
            True,
        )
    if PLUGIN_NAME not in enabled:
        return WiringItem(
            name,
            False,
            f"installed at {target}, but not on Hermes's plugins.enabled list, so it never loads",
            enable,
            True,
        )
    try:
        settings = json.loads((target / "config.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        settings = {}
    settings = settings if isinstance(settings, dict) else {}
    pinned = settings.get("project")
    python = settings.get("python")
    reinstall = "neuralmind install-hermes-plugin"
    if isinstance(pinned, str) and pinned:
        if Path(pinned).resolve() != project.resolve():
            return WiringItem(
                name,
                False,
                f"enabled in {where}, but pinned to {pinned}: every Hermes session there is "
                "served and recorded as that project (to pin this one instead: "
                f"{reinstall} {shell_arg(str(project))})",
                fix=f"{reinstall} --unpin",
                host=True,
                suggest=False,
            )
        serves = "pinned to this project"
    else:
        serves = "serves the directory Hermes works in (TERMINAL_CWD)"
    problems: list[str] = []
    if isinstance(python, str) and python and not Path(python).exists():
        problems.append(f"the interpreter it records, {python}, no longer exists")
    try:
        found = _PLUGIN_VERSION.search((target / "plugin.yaml").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        found = None
    plugin_version = found.group(1) if found else None
    if plugin_version and plugin_version != __version__:
        problems.append(f"its code is from v{plugin_version}, NeuralMind is v{__version__}")
    if problems:
        managed = managed_by_hermes(home)
        detail = f"enabled in {where}, {serves}; but {'; '.join(problems)}"
        if managed is None:
            # install-hermes-plugin leaves the code alone while Hermes's install
            # records can't be read, so re-running it wouldn't update anything.
            records = home / "plugins" / ".install-metadata.json"
            return WiringItem(
                name,
                True,
                f"{detail}. {records} can't be read, so a re-install leaves the code "
                f"alone: fix or delete it, then: {reinstall}",
                host=True,
                outdated=True,
                suggest=False,
            )
        fix = f"hermes plugins update {PLUGIN_NAME}" if managed else reinstall
        return WiringItem(name, True, detail, fix, host=True, outdated=True)
    return WiringItem(name, True, f"enabled in {where}, {serves}", host=True)


# --------------------------------------------------------------------------- #
# MCP registrations
# --------------------------------------------------------------------------- #
def _claude_json_scopes(project: Path) -> list[str]:
    """Claude Code scopes in ``~/.claude.json`` (``claude mcp add``) registering NeuralMind."""
    from .mcp_install import _home, _launches_neuralmind

    try:
        data = json.loads((_home() / ".claude.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    if not isinstance(data, dict):
        return []
    scopes = []
    if _servers_launch(data.get("mcpServers"), _launches_neuralmind):
        scopes.append("user scope, ~/.claude.json")
    projects = data.get("projects")
    local = projects.get(str(project.resolve())) if isinstance(projects, dict) else None
    if isinstance(local, dict) and _servers_launch(local.get("mcpServers"), _launches_neuralmind):
        scopes.append("local scope, ~/.claude.json")
    return scopes


def _cursor_global_scope() -> list[str]:
    """Cursor's user-wide ``~/.cursor/mcp.json``, beside the project file install writes."""
    from .mcp_install import _home, _launches_neuralmind

    data = _read_json(_home() / ".cursor" / "mcp.json")
    servers = data.get("mcpServers") if isinstance(data, dict) else None
    return (
        ["user scope, ~/.cursor/mcp.json"] if _servers_launch(servers, _launches_neuralmind) else []
    )


def _servers_launch(servers, launches) -> bool:
    return isinstance(servers, dict) and any(
        isinstance(entry, dict) and launches(entry) for entry in servers.values()
    )


def mcp_items(project: Path, project_arg: str | None = None) -> list[WiringItem]:
    """One item per MCP client that has NeuralMind registered or looks installed."""
    try:
        from . import mcp_install
    except Exception as exc:  # pragma: no cover - diagnostic must never raise
        return [WiringItem("MCP registration", None, f"could not check ({exc})")]
    items: list[WiringItem] = []
    for client in mcp_install.CLIENTS:
        label = f"MCP registration ({client})"
        try:
            state = mcp_install.registration(client, project)
            scopes = {
                "claude-code": lambda: _claude_json_scopes(project),
                "cursor": _cursor_global_scope,
            }
            extra = scopes[client]() if client in scopes else []
        except Exception as exc:  # pragma: no cover - diagnostic must never raise
            items.append(WiringItem(label, None, f"could not check ({exc})", host=True))
            continue
        install = f"neuralmind install-mcp --client {client}"
        if client in ("claude-code", "cursor") and project_arg not in (None, "."):
            install = f"neuralmind install-mcp {_arg(project, project_arg)} --client {client}"
        where = [str(state.path)] if state.registered else []
        where += extra
        if state.registered or extra:
            if state.disabled:
                # Someone turned it off in Hermes: doctor says how to turn it
                # back on, build doesn't offer to. `hermes config set` splits
                # its key on dots, so only a plain key gets the command.
                entry = f"mcp_servers.{state.name}"
                plain = bool(_PLAIN_KEY.match(state.name))
                items.append(
                    WiringItem(
                        label,
                        False,
                        f"{entry} in {state.path} starts neuralmind-mcp, but is disabled "
                        "there (enabled: false)"
                        + ("" if plain else "; set enabled: true on that entry in the file"),
                        fix=f"hermes config set {entry}.enabled true" if plain else "",
                        host=True,
                        suggest=False,
                    )
                )
                continue
            items.append(WiringItem(label, True, f"registered ({'; '.join(where)})", host=True))
        elif state.unreadable:
            items.append(
                WiringItem(
                    label,
                    None,
                    f"can't tell: {state.path} {state.unreadable}",
                    host=True,
                )
            )
        elif state.detected and client == "hermes" and state.path.is_symlink():
            # install-mcp won't write through a symlink (a declaratively managed
            # config): the entry goes in its source, by hand.
            items.append(
                WiringItem(
                    label,
                    False,
                    f"{state.path} is a symlink (a managed config?) without NeuralMind's "
                    "entry; install-mcp won't write through it: add the entry where it's managed",
                    fix="neuralmind install-mcp --client hermes --print",
                    host=True,
                    suggest=False,
                )
            )
        elif state.detected:
            items.append(
                WiringItem(
                    label,
                    False,
                    f"{client} looks installed ({state.path}), but NeuralMind isn't registered",
                    fix=install,
                    host=True,
                )
            )
    if not items:
        known = ", ".join(mcp_install.CLIENTS)
        items.append(
            WiringItem(
                "MCP registration",
                False,
                f"none found in the client configs NeuralMind knows ({known}); registered by "
                "hand in another client? Then this is expected. For a known one: "
                "neuralmind install-mcp --client <name>",
                fix="neuralmind install-mcp --print",
                host=True,
                suggest=False,
            )
        )
    return items


# --------------------------------------------------------------------------- #
# Summary
# --------------------------------------------------------------------------- #
INERT = "inert"
PARTIAL = "partial"
WIRED = "wired"


def _checked(
    name: str, probe: Callable[[], WiringItem | list[WiringItem]], host: bool = False
) -> list[WiringItem]:
    """``probe()``'s items, or one "could not check" item if it raises.

    A malformed file one probe reads (a daemon discovery file that isn't an
    object, an unreadable Hermes home) leaves the other lines standing.
    """
    try:
        result = probe()
    except Exception as exc:
        return [WiringItem(name, None, f"could not check ({type(exc).__name__}: {exc})", host=host)]
    return result if isinstance(result, list) else [result]


def _probes(project: Path, project_arg: str | None) -> tuple[list[WiringItem], ...]:
    """``(daemon, Git hooks, Hermes plugin, MCP)`` items, each probe guarded."""
    return (
        _checked("Daemon", daemon_item),
        _checked("Git hooks", lambda: git_hooks_item(project, project_arg)),
        _checked("Hermes plugin", lambda: hermes_plugin_item(project), host=True),
        _checked("MCP registration", lambda: mcp_items(project, project_arg), host=True),
    )


def collect(project: Path, project_arg: str | None = None) -> list[WiringItem]:
    """Every wiring item for ``project``, in doctor's order."""
    return [item for items in _probes(project.resolve(), project_arg) for item in items]


def state(items: list[WiringItem], claude_code_hooks: bool) -> str:
    """``inert`` when no agent host calls NeuralMind, ``wired`` when every item
    that applies is wired, else ``partial``.

    A host doctor couldn't read (a client config with comments, a probe that
    failed) may be wired, so it keeps the verdict at ``partial``, not ``inert``.
    """
    if not claude_code_hooks and not any(i.wired for i in items if i.host):
        if any(i.host and i.wired is None for i in items):
            return PARTIAL
        return INERT
    if not any(i.needs_fix for i in items):
        return WIRED
    return PARTIAL


def next_steps(project: Path, project_arg: str | None = None, limit: int = 2) -> list[str]:
    """Up to ``limit`` lines of commands that wire what isn't wired yet.

    The first line keeps the index fresh (daemon, Git hooks); the second wires
    the agent: Hermes when it's set up on this machine, else Claude Code's
    hooks or MCP when no agent host is wired at all.
    """
    project = project.resolve()
    (daemon,), (hooks,), (hermes,), mcp = _probes(project, project_arg)
    offered = [i for i in (daemon, hooks, hermes, *mcp) if i.needs_fix and i.suggest and i.fix]
    fresh = [i.fix for i in offered if i in (daemon, hooks)]
    agent: list[str] = []
    if hermes.wired is not None:  # Hermes is set up on this machine
        agent = [i.fix for i in offered if i is hermes or i.name == "MCP registration (hermes)"]
    else:
        try:
            claude_hooks = bool(claude_code_hook_scopes(project))
        except Exception:
            claude_hooks = False
        if state([hermes, *mcp], claude_hooks) == INERT:
            # Named with the project, so the commands wire the project just
            # built from whatever directory they're pasted into.
            arg = _arg(project, project_arg)
            detected = any(
                i.wired is False and i.name.startswith("MCP registration (") for i in mcp
            )
            if (Path.home() / ".claude").is_dir():
                agent.append(f"neuralmind install-hooks {arg}")
            elif detected:
                agent.append(f"neuralmind install-mcp {arg} --all")
            else:
                # No client to write to (--all would find none): the entry to paste.
                agent.append("neuralmind install-mcp --print")
    lines = [" && ".join(cmds) for cmds in (fresh, agent) if cmds]
    return lines[:limit]
