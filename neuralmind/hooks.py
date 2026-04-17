"""
hooks.py — Claude Code PostToolUse hook integration
====================================================

Two responsibilities:

1. **install_hooks()** — writes .claude/settings.json (project or global)
   to register NeuralMind's compressors as PostToolUse hooks.

2. **run_hook()** — the runtime entrypoint invoked by Claude Code for each
   tool call. Reads the hook payload from stdin (Claude Code hook protocol),
   transforms the tool output, writes the new payload to stdout.

This file is intentionally kept slim. All compression logic lives in
`compressors.py`; this module only bridges Claude Code's hook contract.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Literal

from .compressors import (
    cap_search_results,
    compress_bash,
    compress_read,
    offload_if_large,
)

# Sentinels delimit the neuralmind block so we can upgrade/remove without
# clobbering other tools' hook contributions.
BLOCK_KEY = "__neuralmind_managed__"
HOOK_VERSION = "1"


def _hook_block() -> dict:
    """Return the canonical neuralmind hook block."""
    return {
        BLOCK_KEY: HOOK_VERSION,
        "PostToolUse": [
            {
                "matcher": "Read",
                "hooks": [{"type": "command", "command": "neuralmind _hook compress-read"}],
            },
            {
                "matcher": "Bash",
                "hooks": [{"type": "command", "command": "neuralmind _hook compress-bash"}],
            },
            {
                "matcher": "Grep",
                "hooks": [{"type": "command", "command": "neuralmind _hook cap-search"}],
            },
        ],
    }


def _settings_path(scope: Literal["project", "global"], project_path: str | None = None) -> Path:
    """Resolve the settings.json path for the given scope."""
    if scope == "global":
        return Path.home() / ".claude" / "settings.json"
    if not project_path:
        raise ValueError("project_path required for project scope")
    return Path(project_path).resolve() / ".claude" / "settings.json"


def install_hooks(
    scope: Literal["project", "global"] = "project",
    project_path: str | None = None,
    uninstall: bool = False,
) -> dict:
    """Install or remove NeuralMind's PostToolUse hooks.

    Args:
        scope: "project" writes <project>/.claude/settings.json;
               "global" writes ~/.claude/settings.json
        project_path: required when scope="project"
        uninstall: if True, remove only neuralmind hooks, preserve others

    Returns:
        Dict with action taken and settings path
    """
    path = _settings_path(scope, project_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    # Load existing settings (or start fresh)
    existing: dict = {}
    if path.exists():
        try:
            existing = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            existing = {}

    # Strip any prior neuralmind block by filtering hooks
    # Claude Code's schema: settings.hooks.<Event> = list of matcher blocks
    hooks = existing.get("hooks", {})
    for event in ("PostToolUse", "PreToolUse", "Stop", "SessionStart", "UserPromptSubmit"):
        if event not in hooks:
            continue
        if not isinstance(hooks[event], list):
            continue
        hooks[event] = [
            block for block in hooks[event]
            if not _is_neuralmind_block(block)
        ]
        if not hooks[event]:
            del hooks[event]

    if uninstall:
        # Just save the cleaned settings
        if hooks:
            existing["hooks"] = hooks
        else:
            existing.pop("hooks", None)
        if not existing:
            path.unlink(missing_ok=True)
            return {"action": "uninstalled", "path": str(path), "removed_file": True}
        path.write_text(json.dumps(existing, indent=2), encoding="utf-8")
        return {"action": "uninstalled", "path": str(path)}

    # Install: append our block
    block = _hook_block()
    for event in ("PostToolUse",):  # only event we use today
        hooks.setdefault(event, []).extend(block[event])

    existing["hooks"] = hooks
    path.write_text(json.dumps(existing, indent=2), encoding="utf-8")
    return {"action": "installed", "path": str(path), "scope": scope}


def _is_neuralmind_block(block: dict) -> bool:
    """True if a hook-matcher block was installed by neuralmind.

    Claude Code matcher blocks don't carry arbitrary metadata, so we
    identify our blocks by the command they run. Safe because other
    tools' commands will differ.
    """
    if not isinstance(block, dict):
        return False
    for h in block.get("hooks") or []:
        cmd = (h or {}).get("command", "")
        if "neuralmind _hook" in cmd:
            return True
    return False


# -----------------------------------------------------------------------------
# Hook runtime — executed per tool call by Claude Code
# -----------------------------------------------------------------------------

def run_hook(action: str) -> int:
    """Entry point for `neuralmind _hook <action>`.

    Reads a JSON payload from stdin (Claude Code hook protocol), transforms
    the tool output, writes new JSON to stdout.

    Claude Code hook payload (PostToolUse) contains:
      - tool_name: "Read" | "Bash" | "Grep" | ...
      - tool_input: dict of args passed to the tool
      - tool_response: dict including `output` (stdout) or `content`

    Our response schema (per Claude Code docs): we can emit a
    `stdout_override` or equivalent — exact key may vary by hook version.
    We implement the safest behavior: print the transformed output to
    stdout; Claude Code captures it and forwards to the model.

    If compression fails or is not applicable, print nothing (fail open).
    """
    try:
        raw = sys.stdin.read()
        if not raw.strip():
            return 0
        payload = json.loads(raw)
    except Exception:
        return 0  # fail open

    tool_input = payload.get("tool_input") or {}
    tool_response = payload.get("tool_response") or {}

    # Skip if user explicitly bypassed
    if os.environ.get("NEURALMIND_BYPASS") == "1":
        return 0

    if action == "compress-read":
        file_path = tool_input.get("file_path") or tool_input.get("path") or ""
        content = (
            tool_response.get("content")
            or tool_response.get("output")
            or tool_response.get("text")
            or ""
        )
        if not (file_path and content):
            return 0
        compressed = compress_read(file_path, content)
        if compressed != content:
            _emit(compressed)
        return 0

    if action == "compress-bash":
        stdout = tool_response.get("stdout") or tool_response.get("output") or ""
        stderr = tool_response.get("stderr") or ""
        exit_code = int(tool_response.get("exit_code") or tool_response.get("returncode") or 0)
        if not (stdout or stderr):
            return 0
        compressed = compress_bash(stdout, stderr, exit_code)
        _emit(compressed)
        return 0

    if action == "cap-search":
        content = (
            tool_response.get("content")
            or tool_response.get("output")
            or ""
        )
        if not content:
            return 0
        capped = cap_search_results(content)
        if capped != content:
            _emit(capped)
        return 0

    if action == "offload":
        content = tool_response.get("content") or tool_response.get("output") or ""
        if not content:
            return 0
        compressed, _ = offload_if_large(content)
        if compressed != content:
            _emit(compressed)
        return 0

    return 0


def _emit(transformed: str) -> None:
    """Emit a JSON response that tells Claude Code to use our transformed output.

    Claude Code's hook schema supports returning a JSON object with
    `hookSpecificOutput.additionalContext` on PostToolUse. We include the
    transformed output there so the model sees it.
    """
    response = {
        "hookSpecificOutput": {
            "hookEventName": "PostToolUse",
            "additionalContext": transformed,
        },
    }
    sys.stdout.write(json.dumps(response))
    sys.stdout.flush()
