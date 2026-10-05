"""MCP auto-detection + one-command registration for AI coding agents.

NeuralMind ships an MCP server (the ``neuralmind-mcp`` console script). The
distribution moat is making an agent *find* it with zero fuss: every major
client — Claude Code, Cursor, Cline, Claude Desktop — reads the same
``{"mcpServers": {...}}`` shape, just from different files. This module
detects which clients are installed and merges a NeuralMind entry into their
config without clobbering anything else.

Pure standard library (json + pathlib + os), so it's unit-testable with a fake
``HOME`` and never imports the heavy retrieval stack.
"""

from __future__ import annotations

import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path

SERVER_NAME = "neuralmind"
SERVER_COMMAND = "neuralmind-mcp"

# The clients we know how to register with. Each reads a JSON document with a
# top-level ``mcpServers`` object mapping a name → a launch spec.
CLIENTS = ("claude-code", "cursor", "cline", "claude-desktop", "vscode")


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


def config_path(client: str, project_dir: Path) -> Path:
    """Where ``client`` reads MCP servers from for ``project_dir``.

    Claude Code and Cursor are *project-scoped* (a file in the repo); Claude
    Desktop and Cline are *user-scoped* (a per-machine file).
    """
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


def is_detected(client: str, project_dir: Path) -> bool:
    """True when ``client`` looks installed: its config file exists, or the
    user-scoped clients' config directory exists."""
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
    entry = server_entry(command)
    existing = servers.get(SERVER_NAME)
    if existing == entry:
        return config, "already-present"
    action = "updated" if SERVER_NAME in servers else "installed"
    servers[SERVER_NAME] = entry
    return config, action


def merge_server_vscode(config: dict, command: str = SERVER_COMMAND) -> tuple[dict, str]:
    """Add/update NeuralMind's entry in a VS Code settings.json dict.

    VS Code 1.99+ uses the ``"mcp.servers"`` top-level key (not ``"mcpServers"``).
    Other settings in the file are preserved untouched.
    """
    servers = config.get("mcp.servers")
    if not isinstance(servers, dict):
        servers = {}
        config["mcp.servers"] = servers
    entry = server_entry(command)
    existing = servers.get(SERVER_NAME)
    if existing == entry:
        return config, "already-present"
    action = "updated" if SERVER_NAME in servers else "installed"
    servers[SERVER_NAME] = entry
    return config, action


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
) -> InstallResult:
    """Merge NeuralMind into ``client``'s config, writing the file."""
    path = config_path(client, project_dir)
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


def detect_clients(project_dir: Path) -> list[str]:
    """The known clients that look installed for this project/machine."""
    return [c for c in CLIENTS if is_detected(c, project_dir)]


def snippet(command: str = SERVER_COMMAND) -> str:
    """The config snippet to paste into any MCP client by hand."""
    return json.dumps({"mcpServers": {SERVER_NAME: server_entry(command)}}, indent=2)
