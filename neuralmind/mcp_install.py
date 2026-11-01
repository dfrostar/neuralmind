# SPDX-License-Identifier: MIT
"""MCP auto-detection + one-command registration for AI coding agents.

NeuralMind ships an MCP server (the ``neuralmind-mcp`` console script). The
distribution moat is making an agent *find* it with zero fuss: every major
client — Claude Code, Cursor, Cline, Claude Desktop — reads the same
``{"mcpServers": {...}}`` shape, just from different files. Hermes-Agent keeps
the same launch spec under ``mcp_servers:`` in its YAML ``config.yaml``. This
module detects which clients are installed and merges a NeuralMind entry into
their config without clobbering anything else.

Standard library (json + pathlib + os), plus PyYAML (a core dependency) for
Hermes's config only, so it's unit-testable with a fake ``HOME`` and never
imports the heavy retrieval stack.
"""

from __future__ import annotations

import contextlib
import json
import os
import re
import stat
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

SERVER_NAME = "neuralmind"
SERVER_COMMAND = "neuralmind-mcp"

# The clients we know how to register with. Each reads a JSON document with a
# top-level ``mcpServers`` object mapping a name → a launch spec, except Hermes
# (YAML, ``mcp_servers:``) and VS Code (``mcp.servers`` in its settings).
CLIENTS = ("claude-code", "cursor", "cline", "claude-desktop", "vscode", "hermes")


def server_entry(command: str = SERVER_COMMAND) -> dict:
    """The ``mcpServers`` value for NeuralMind. The MCP tools take a
    ``project_path`` argument per call, so the launch spec needs no args."""
    return {"command": command, "args": []}


# --------------------------------------------------------------------------- #
# Per-client config locations
# --------------------------------------------------------------------------- #
def _home() -> Path:
    return Path(os.environ.get("HOME") or os.path.expanduser("~"))


def _claude_desktop_path() -> Path:
    """Platform config path for the Claude Desktop app."""
    if sys.platform == "darwin":
        return _home() / "Library" / "Application Support" / "Claude" / "claude_desktop_config.json"
    if os.name == "nt":
        base = os.environ.get("APPDATA") or str(_home() / "AppData" / "Roaming")
        return Path(base) / "Claude" / "claude_desktop_config.json"
    return _home() / ".config" / "Claude" / "claude_desktop_config.json"


def _vscode_settings_path() -> Path:
    """VS Code user settings.json (native MCP support added in VS Code 1.99)."""
    if sys.platform == "darwin":
        base = _home() / "Library" / "Application Support" / "Code" / "User"
    elif os.name == "nt":
        base = (
            Path(os.environ.get("APPDATA") or str(_home() / "AppData" / "Roaming"))
            / "Code"
            / "User"
        )
    else:
        base = _home() / ".config" / "Code" / "User"
    return base / "settings.json"


def _cline_path() -> Path:
    """Cline stores MCP settings under the VS Code extension's globalStorage."""
    if sys.platform == "darwin":
        base = _home() / "Library" / "Application Support"
    elif os.name == "nt":
        base = Path(os.environ.get("APPDATA") or str(_home() / "AppData" / "Roaming"))
    else:
        base = _home() / ".config"
    return (
        base
        / "Code"
        / "User"
        / "globalStorage"
        / "saoudrizwan.claude-dev"
        / "settings"
        / "cline_mcp_settings.json"
    )


def _hermes_install():
    """:mod:`neuralmind.hermes_install` (stdlib-only too), which knows the Hermes home.

    Loaded beside this file when this module was itself loaded as a standalone
    file, as the stdlib-only tests do, so a relative import has no package.
    """
    try:
        from . import hermes_install
    except ImportError:
        import importlib.util

        name = "neuralmind_hermes_install"
        if name in sys.modules:
            return sys.modules[name]
        spec = importlib.util.spec_from_file_location(
            name, Path(__file__).with_name("hermes_install.py")
        )
        if spec is None or spec.loader is None:
            raise ImportError(f"can't load {name} beside {__file__}") from None
        hermes_install = importlib.util.module_from_spec(spec)
        sys.modules[name] = hermes_install
        spec.loader.exec_module(hermes_install)
    return hermes_install


def config_path(client: str, project_dir: Path, hermes_home: Path | None = None) -> Path:
    """Where ``client`` reads MCP servers from for ``project_dir``.

    Claude Code and Cursor are *project-scoped* (a file in the repo); Claude
    Desktop, Cline and Hermes are *user-scoped* (a per-machine file). Hermes's
    is ``config.yaml`` in ``hermes_home``, else the Hermes home plain
    ``hermes`` runs in (its active profile, ``$HERMES_HOME``, or ``~/.hermes``).
    """
    if client == "hermes":
        return (hermes_home or _hermes_install().hermes_home()) / "config.yaml"
    if client == "claude-code":
        return project_dir / ".mcp.json"
    if client == "cursor":
        return project_dir / ".cursor" / "mcp.json"
    if client == "claude-desktop":
        return _claude_desktop_path()
    if client == "cline":
        return _cline_path()
    if client == "vscode":
        return _vscode_settings_path()
    raise ValueError(f"unknown client {client!r}; known: {', '.join(CLIENTS)}")


def is_detected(client: str, project_dir: Path, hermes_home: Path | None = None) -> bool:
    """True when ``client`` looks installed: its config file exists, or the
    user-scoped clients' config directory exists. Hermes counts once its
    ``config.yaml`` exists: the installer adds to that file and never creates
    it, so a home with only ``.env`` or ``state.db`` has nothing to register in."""
    if client == "hermes":
        return config_path(client, project_dir, hermes_home).exists()
    path = config_path(client, project_dir)
    if path.exists():
        return True
    # Project-scoped clients aren't "detected" until they have a file; for
    # user-scoped clients, the presence of the app's config dir is the signal.
    if client in ("claude-desktop", "cline", "vscode"):
        return path.parent.exists()
    return False


# --------------------------------------------------------------------------- #
# Merge logic (pure)
# --------------------------------------------------------------------------- #
def _launches_neuralmind(entry: dict) -> bool:
    """True when an existing entry already starts NeuralMind's MCP server —
    an absolute venv path to ``neuralmind-mcp`` or ``python -m
    neuralmind.mcp_server`` — however it differs from the default."""
    command = entry.get("command")
    args = entry.get("args") if isinstance(entry.get("args"), list) else []
    if isinstance(command, str) and Path(command.replace("\\", "/")).name in (
        SERVER_COMMAND,
        f"{SERVER_COMMAND}.exe",
    ):
        return True
    return any(arg in ("neuralmind.mcp_server", SERVER_COMMAND) for arg in args)


def _merge_entry(servers: dict, command: str) -> str:
    """Add/update NeuralMind's entry in a ``servers`` mapping in place.

    An entry that already launches NeuralMind is kept as the user wrote it
    (MCP clients often start servers with a minimal PATH, so an absolute
    command can be load-bearing); otherwise the launch spec is replaced. Any
    other keys the user added (``env``, ``cwd``, …) are kept either way.
    Returns ``installed``, ``updated`` or ``already-present``.
    """
    existing = servers.get(SERVER_NAME)
    if not isinstance(existing, dict):
        action = "updated" if SERVER_NAME in servers else "installed"
        servers[SERVER_NAME] = server_entry(command)
        return action
    if _launches_neuralmind(existing):
        return "already-present"
    servers[SERVER_NAME] = {**existing, **server_entry(command)}
    return "updated"


def merge_server(config: dict, command: str = SERVER_COMMAND) -> tuple[dict, str]:
    """Add/update NeuralMind's entry in a config dict's ``mcpServers``.

    Returns ``(config, action)`` where action is ``installed`` (newly added),
    ``updated`` (changed an existing entry), or ``already-present`` (no change).
    Other servers are preserved untouched.
    """
    servers = config.get("mcpServers")
    if not isinstance(servers, dict):
        servers = {}
        config["mcpServers"] = servers
    return config, _merge_entry(servers, command)


def merge_server_vscode(config: dict, command: str = SERVER_COMMAND) -> tuple[dict, str]:
    """Add/update NeuralMind's entry in a VS Code settings.json dict.

    VS Code 1.99+ reads ``"mcp.servers"``, or the same mapping nested as
    ``"mcp": {"servers": …}``; an existing nested one is used rather than
    adding a second, dotted key beside it. Other settings are preserved.
    """
    nested = config.get("mcp")
    if (
        "mcp.servers" not in config
        and isinstance(nested, dict)
        and isinstance(nested.get("servers"), dict)
    ):
        return config, _merge_entry(nested["servers"], command)
    servers = config.get("mcp.servers")
    if not isinstance(servers, dict):
        servers = {}
        config["mcp.servers"] = servers
    return config, _merge_entry(servers, command)


def _read_config(path: Path) -> tuple[dict, str, str]:
    """Read a client's JSON config.  Returns ``(config, skip_action, why)``.

    ``skip_action`` is empty when the file is absent, blank, or a JSON object we
    can round-trip. Otherwise the file must NOT be rewritten — it is JSONC
    (comments / trailing commas, common in Cursor, Cline and VS Code configs),
    has a non-object top level, or can't be read — and treating it as ``{}``
    would delete every other server the user configured.
    """
    if not path.exists():
        return {}, "", ""
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        return {}, "skipped-unreadable", f"could not be read ({exc})"
    if not text.strip():
        return {}, "", ""
    try:
        data = json.loads(text)
    except ValueError:
        return {}, "skipped-jsonc", "is not strict JSON (comments or a trailing comma?)"
    if not isinstance(data, dict):
        return {}, "skipped-not-object", "does not hold a JSON object at the top level"
    return data, "", ""


@dataclass
class InstallResult:
    client: str
    path: Path
    action: str  # installed | updated | already-present | skipped-<reason>
    detail: str = ""  # for a skip: why, and the entry to add by hand

    def to_dict(self) -> dict:
        out = {"client": self.client, "path": str(self.path), "action": self.action}
        if self.detail:
            out["detail"] = self.detail
        return out


def install(
    client: str,
    project_dir: Path,
    command: str = SERVER_COMMAND,
    *,
    create_parents: bool = True,
    hermes_home: Path | None = None,
) -> InstallResult:
    """Merge NeuralMind into ``client``'s config, writing the file."""
    path = config_path(client, project_dir, hermes_home)
    if client == "hermes":
        return install_hermes(path, command)
    config, skip_action, why = _read_config(path)
    if skip_action:
        key = "mcp.servers" if client == "vscode" else "mcpServers"
        entry = json.dumps({key: {SERVER_NAME: server_entry(command)}}, indent=2)
        return InstallResult(
            client=client,
            path=path,
            action=skip_action,
            detail=f"{path} {why}; left untouched. Add this entry by hand:\n{entry}",
        )
    if client == "vscode":
        config, action = merge_server_vscode(config, command)
    else:
        config, action = merge_server(config, command)
    if action != "already-present":
        if create_parents:
            path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")
    return InstallResult(client=client, path=path, action=action)


# --------------------------------------------------------------------------- #
# Hermes-Agent: YAML, edited as text
# --------------------------------------------------------------------------- #
# Hermes rewrites config.yaml itself with comments preserved; loading and
# dumping it here would drop them. So the entry is added as text, under an
# existing block-style ``mcp_servers:`` or as a new block at the end, and only
# written when the result parses to the old config plus that entry.
HERMES_KEY = "mcp_servers"
_HERMES_KEY_LINE = re.compile(r"^mcp_servers\s*:\s*(?:#.*)?$")
_PLAIN_SCALAR = re.compile(r"^[A-Za-z0-9_./-]+$")


def _yaml_scalar(value: str) -> str:
    # A JSON string is a valid YAML double-quoted scalar.
    return value if _PLAIN_SCALAR.match(value) else json.dumps(value)


def hermes_snippet(command: str = SERVER_COMMAND) -> str:
    """The ``config.yaml`` entry to paste into Hermes by hand."""
    return f"{HERMES_KEY}:\n  {SERVER_NAME}:\n    command: {_yaml_scalar(command)}\n    args: []\n"


def _hermes_insert(text: str, command: str) -> str | None:
    """``text`` with NeuralMind's entry added; None when ``mcp_servers`` isn't block style."""
    nl = "\r\n" if "\r\n" in text else "\n"
    lines = text.splitlines(keepends=True)
    for i, line in enumerate(lines):
        if not _HERMES_KEY_LINE.match(line.rstrip("\r\n")):
            continue
        indent = "  "
        for following in lines[i + 1 :]:
            stripped = following.strip()
            if not stripped or stripped.startswith("#"):
                continue
            lead = following[: len(following) - len(following.lstrip(" "))]
            indent = lead or indent
            break
        entry = (
            f"{indent}{SERVER_NAME}:{nl}"
            f"{indent}{indent}command: {_yaml_scalar(command)}{nl}"
            f"{indent}{indent}args: []{nl}"
        )
        head = "".join(lines[: i + 1])
        if not head.endswith("\n"):
            head += nl
        return head + entry + "".join(lines[i + 1 :])
    if re.search(r"^mcp_servers\s*:", text, re.MULTILINE):
        return None  # flow style (`mcp_servers: {...}`) or something stranger
    sep = nl if text and not text.endswith("\n") else ""
    return text + sep + hermes_snippet(command).replace("\n", nl)


def _hermes_entry_disabled(entry: dict) -> bool:
    """Hermes reads ``enabled`` as a boolean-ish value, defaulting to on."""
    value = entry.get("enabled", True)
    if isinstance(value, str):
        return value.strip().lower() in ("false", "no", "off", "0")
    return value is False or value == 0


def _hermes_skip(path: Path, action: str, why: str, command: str) -> InstallResult:
    return InstallResult(
        client="hermes",
        path=path,
        action=action,
        detail=f"{path} {why}; left untouched. Add this entry by hand:\n{hermes_snippet(command)}",
    )


def install_hermes(path: Path, command: str = SERVER_COMMAND) -> InstallResult:
    """Add NeuralMind under ``mcp_servers:`` in Hermes's ``config.yaml``.

    Never creates the file: a ``config.yaml`` is one of the markers Hermes
    takes for a set-up home, so writing one would skip its first-run setup.
    """
    import yaml

    if not path.exists():
        return _hermes_skip(
            path,
            "skipped-no-hermes-config",
            "doesn't exist (set Hermes up first by running `hermes`)",
            command,
        )
    if path.is_symlink():
        return _hermes_skip(
            path, "skipped-symlink", "is a symlink (a declaratively managed config?)", command
        )
    try:
        raw = path.read_bytes()
        bom = raw.startswith(b"\xef\xbb\xbf")
        text = raw.decode("utf-8-sig")
    except (OSError, UnicodeDecodeError) as exc:
        return _hermes_skip(path, "skipped-unreadable", f"could not be read ({exc})", command)
    try:
        data = yaml.safe_load(text)
    except Exception:  # YAMLError, or a ValueError from a scalar like `2001-13-45`
        return _hermes_skip(path, "skipped-invalid-yaml", "is not valid YAML", command)
    if data is None:
        data = {}
    servers = data.get(HERMES_KEY) if isinstance(data, dict) else None
    if not isinstance(data, dict) or not isinstance(servers, (dict, type(None))):
        return _hermes_skip(
            path, "skipped-not-object", f"does not hold a {HERMES_KEY} mapping", command
        )
    # NeuralMind under any key counts: a second entry would start a second
    # server, with every tool twice. An enabled entry first.
    matches = [
        (str(key), entry)
        for key, entry in (servers or {}).items()
        if isinstance(entry, dict) and _launches_neuralmind(entry)
    ]
    if matches:
        matches.sort(key=lambda m: (_hermes_entry_disabled(m[1]), m[0] != SERVER_NAME))
        key, entry = matches[0]
        notes = []
        if key != SERVER_NAME:
            notes.append(f"registered as {HERMES_KEY}.{key}")
        if _hermes_entry_disabled(entry):
            notes.append(f"disabled there: set {HERMES_KEY}.{key}.enabled: true to use it")
        return InstallResult(
            client="hermes", path=path, action="already-present", detail="; ".join(notes)
        )
    existing = (servers or {}).get(SERVER_NAME)
    if existing is not None:
        return _hermes_skip(
            path,
            "skipped-conflict",
            f"already has a {HERMES_KEY}.{SERVER_NAME} entry that doesn't start neuralmind-mcp",
            command,
        )
    new_text = _hermes_insert(text, command)
    expected = {**data, HERMES_KEY: {**(servers or {}), SERVER_NAME: server_entry(command)}}
    try:
        merged = yaml.safe_load(new_text) if new_text is not None else None
    except Exception:
        merged = None
    if new_text is None or merged != expected:
        return _hermes_skip(
            path,
            "skipped-unmergeable",
            "couldn't take the entry without other changes",
            command,
        )
    try:
        _replace_keeping_owner(path, (b"\xef\xbb\xbf" if bom else b"") + new_text.encode("utf-8"))
    except OSError as exc:
        return _hermes_skip(path, "skipped-unwritable", f"could not be written ({exc})", command)
    return InstallResult(client="hermes", path=path, action="installed")


def _replace_keeping_owner(path: Path, data: bytes) -> None:
    """Replace ``path`` with ``data`` atomically, keeping its mode and owner.

    The temporary file is unique (two runs can't swap in each other's half-
    written file) and starts at 0600, since config.yaml can hold credentials;
    it then takes the old file's mode. Run as root against a user's home
    (``sudo -E``), it is given back to the file's owner, as Hermes's own writer
    does, so Hermes can still read its config.
    """
    st = path.stat()
    fd, name = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.", suffix=".neuralmind-tmp")
    tmp = Path(name)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
        os.chmod(tmp, stat.S_IMODE(st.st_mode))
        if hasattr(os, "geteuid") and os.geteuid() == 0 and st.st_uid != 0:
            os.chown(tmp, st.st_uid, st.st_gid)
        os.replace(tmp, path)
    except OSError:
        with contextlib.suppress(OSError):
            tmp.unlink()
        raise


# --------------------------------------------------------------------------- #
# Read-only registration state (doctor, install-hermes-plugin)
# --------------------------------------------------------------------------- #
@dataclass
class Registration:
    client: str
    path: Path
    detected: bool
    registered: bool = False  # an entry, under any name, starts neuralmind-mcp
    disabled: bool = False  # Hermes: every such entry has enabled: false
    name: str = ""  # that entry's key, which a fix must name
    unreadable: str = ""  # why the config couldn't be read, so the answer is unknown


def _servers_of(client: str, config: dict) -> dict:
    if client == "vscode":
        nested = config.get("mcp")
        servers = config.get("mcp.servers")
        if servers is None and isinstance(nested, dict):
            servers = nested.get("servers")
    else:
        servers = config.get(HERMES_KEY if client == "hermes" else "mcpServers")
    return servers if isinstance(servers, dict) else {}


def registration(client: str, project_dir: Path, hermes_home: Path | None = None) -> Registration:
    """Whether ``client``'s config registers NeuralMind, without writing anything."""
    path = config_path(client, project_dir, hermes_home)
    state = Registration(client, path, is_detected(client, project_dir, hermes_home))
    if not path.exists():
        return state
    if client == "hermes":
        try:
            import yaml

            config = yaml.safe_load(path.read_text(encoding="utf-8-sig")) or {}
        except Exception as exc:
            state.unreadable = f"could not be read as YAML ({type(exc).__name__})"
            return state
        if not isinstance(config, dict):
            return state
    else:
        config, skip_action, why = _read_config(path)
        if skip_action:
            state.unreadable = why
            return state
    servers = _servers_of(client, config)
    matches = [
        (key, entry)
        for key, entry in servers.items()
        if isinstance(entry, dict) and _launches_neuralmind(entry)
    ]
    if matches:
        off = _hermes_entry_disabled if client == "hermes" else (lambda _entry: False)
        # An enabled entry first, then the name install writes.
        matches.sort(key=lambda m: (off(m[1]), m[0] != SERVER_NAME))
        state.name, entry = str(matches[0][0]), matches[0][1]
        state.registered = True
        state.disabled = off(entry)
    return state


def detect_clients(project_dir: Path) -> list[str]:
    """The known clients that look installed for this project/machine."""
    return [c for c in CLIENTS if is_detected(c, project_dir)]


def snippet(command: str = SERVER_COMMAND) -> str:
    """The config snippet to paste into any MCP client by hand."""
    return json.dumps({"mcpServers": {SERVER_NAME: server_entry(command)}}, indent=2)
