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
    """Return the canonical neuralmind hook block.

    PostToolUse: token-saving compressors for Read/Bash/Grep output.
    SessionStart: warm the synapse store and run a decay tick.
    UserPromptSubmit: inject spreading-activation neighbors as context.
    PreCompact: normalize hubs before context shrinks.
    """
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
        "SessionStart": [
            {
                "hooks": [{"type": "command", "command": "neuralmind _hook session-start"}],
            },
        ],
        "UserPromptSubmit": [
            {
                "hooks": [{"type": "command", "command": "neuralmind _hook prompt-submit"}],
            },
        ],
        "PreCompact": [
            {
                "hooks": [{"type": "command", "command": "neuralmind _hook pre-compact"}],
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
    for event in (
        "PostToolUse",
        "PreToolUse",
        "Stop",
        "SessionStart",
        "UserPromptSubmit",
        "PreCompact",
    ):
        if event not in hooks:
            continue
        if not isinstance(hooks[event], list):
            continue
        hooks[event] = [block for block in hooks[event] if not _is_neuralmind_block(block)]
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
    for event in ("PostToolUse", "SessionStart", "UserPromptSubmit", "PreCompact"):
        if event in block:
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
        content = tool_response.get("content") or tool_response.get("output") or ""
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

    if action == "session-start":
        # Warm the synapse store, run one decay tick, then export the
        # learned associations as a markdown memory file so Claude Code's
        # auto-memory system picks it up on this very session.
        cwd = payload.get("cwd") or os.getcwd()
        store = _open_synapses(cwd)
        if store is None:
            return 0
        try:
            store.decay()
        except Exception:
            pass
        if os.environ.get("NEURALMIND_SYNAPSE_EXPORT") != "0":
            try:
                from .synapse_memory import export_synapse_memory

                export_synapse_memory(cwd)
            except Exception:
                pass
        return 0

    if action == "prompt-submit":
        # Inject spreading-activation neighbors for the user's prompt as
        # additional context. Cheap: one search to seed, one spread over
        # the synapse graph.
        cwd = payload.get("cwd") or os.getcwd()
        prompt = (payload.get("prompt") or "").strip()
        if not prompt or os.environ.get("NEURALMIND_SYNAPSE_INJECT") == "0":
            return 0
        injected = _spread_for_prompt(cwd, prompt)
        if injected:
            _emit_for_event("UserPromptSubmit", injected)
        return 0

    if action == "pre-compact":
        # Before the agent compacts its context, take the chance to
        # normalize any runaway hub nodes — keeps retrieval balanced
        # across sessions.
        cwd = payload.get("cwd") or os.getcwd()
        store = _open_synapses(cwd)
        if store is None:
            return 0
        try:
            store.normalize_hubs()
        except Exception:
            pass
        return 0

    return 0


def _open_synapses(project_path: str):
    """Open the synapse store for a project without forcing a build.

    Hooks must stay fast and never raise — fall through to None on any
    failure so we don't disrupt the user's session.
    """
    try:
        from .synapses import SynapseStore, default_db_path

        return SynapseStore(default_db_path(project_path))
    except Exception:
        return None


def _spread_for_prompt(project_path: str, prompt: str, top_k: int = 8) -> str:
    """Run spreading activation for a prompt and format it as injected context.

    Returns an empty string when the synapse graph has no learned edges
    yet (cold start) or when anything goes wrong — hooks must fail open.
    """
    try:
        from .core import NeuralMind

        mind = NeuralMind(project_path)
        ranked = mind.synaptic_neighbors(prompt, depth=2, top_k=top_k)
    except Exception:
        return ""
    if not ranked:
        return ""
    lines = ["## NeuralMind associative recall", ""]
    for node_id, energy in ranked:
        lines.append(f"- {node_id} (activation {energy:.2f})")
    return "\n".join(lines)


def _emit_for_event(event_name: str, content: str) -> None:
    """Emit hookSpecificOutput for a non-PostToolUse event."""
    response = {
        "hookSpecificOutput": {
            "hookEventName": event_name,
            "additionalContext": content,
        },
    }
    sys.stdout.write(json.dumps(response))
    sys.stdout.flush()


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
