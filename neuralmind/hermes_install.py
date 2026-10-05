"""hermes_install.py — install NeuralMind's Hermes-Agent plugin.

``neuralmind install-hermes-plugin`` writes a directory plugin into the Hermes
home (``$HERMES_HOME``, else ``~/.hermes``):

- ``plugins/neuralmind/__init__.py`` — a copy of :mod:`neuralmind.hermes_plugin`
- ``plugins/neuralmind/plugin.yaml`` — the manifest Hermes discovers it by
- ``plugins/neuralmind/config.json`` — the Python interpreter that has
  NeuralMind installed, and the project, if one was given

then runs ``hermes plugins enable neuralmind``: Hermes loads a user plugin only
once it's on the ``plugins.enabled`` list. Re-running updates the copy in place.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

PLUGIN_NAME = "neuralmind"

MANIFEST = """\
name: neuralmind
version: "{version}"
description: "NeuralMind code memory: related files, decisions and a session recap added to each turn, with no tool call."
author: NeuralMind
provides_hooks:
  - pre_llm_call
  - post_tool_call
"""


def hermes_home() -> Path:
    return Path(os.environ.get("HERMES_HOME") or Path.home() / ".hermes").expanduser()


def plugin_dir(home: Path | None = None) -> Path:
    return (home or hermes_home()) / "plugins" / PLUGIN_NAME


def _hermes(action: str, home: Path) -> bool | None:
    """Run ``hermes plugins <action> neuralmind``; None when Hermes isn't on PATH."""
    hermes = shutil.which("hermes")
    if hermes is None:
        return None
    command = [hermes, "plugins", action, PLUGIN_NAME]
    if action == "enable":
        # The plugin replaces no built-in tool; this also skips that prompt.
        command.append("--no-allow-tool-override")
    try:
        done = subprocess.run(
            command,
            env={**os.environ, "HERMES_HOME": str(home)},
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
            timeout=120,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    return done.returncode == 0


def install(project: str | None = None, home: Path | None = None, enable: bool = True) -> dict:
    """Install (or update) the plugin; returns what was done."""
    from . import __version__

    home = home or hermes_home()
    if not home.is_dir():
        raise FileNotFoundError(
            f"No Hermes home at {home}. Install Hermes-Agent first, or set HERMES_HOME."
        )
    target = plugin_dir(home)
    target.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(Path(__file__).parent / "hermes_plugin" / "__init__.py", target / "__init__.py")
    (target / "plugin.yaml").write_text(MANIFEST.format(version=__version__), encoding="utf-8")
    project_path = str(Path(project).expanduser().resolve()) if project else None
    config = {"python": sys.executable, "project": project_path}
    (target / "config.json").write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")
    return {
        "path": target,
        "project": project_path,
        "built": bool(project_path)
        and (Path(project_path) / ".neuralmind" / "build_status.json").is_file(),
        "enabled": _hermes("enable", home) if enable else None,
    }


def uninstall(home: Path | None = None) -> dict:
    """Disable the plugin in Hermes and remove its directory."""
    home = home or hermes_home()
    target = plugin_dir(home)
    disabled = _hermes("disable", home) if target.exists() else None
    removed = False
    if target.is_dir() and not target.is_symlink():
        shutil.rmtree(target)
        removed = True
    return {"path": target, "removed": removed, "disabled": disabled}
