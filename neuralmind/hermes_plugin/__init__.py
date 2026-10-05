"""NeuralMind for Hermes-Agent — code memory injected into each turn, no tool call.

A Hermes plugin (``~/.hermes/plugins/neuralmind/``, installed and enabled by
``neuralmind install-hermes-plugin``). It gives Hermes what NeuralMind's Claude
Code hooks give Claude Code:

- ``pre_llm_call`` (once per turn, before the model runs): the files and
  decisions related to the user's message, from NeuralMind's synapse layer,
  returned as ``{"context": ...}`` so Hermes appends them to that turn's user
  message. On a session's first turn, the session recap of the previous
  session in the project comes first.
- ``post_tool_call`` on ``write_file`` and ``patch``: the edited file is
  recorded, for the next session's recap and for the synapse layer.

It is a thin, stdlib-only shim. Each action runs ``python -m neuralmind _hook
<action>`` with the same JSON payload Claude Code sends, so Hermes gets the
same behavior, toggles (``NEURALMIND_BYPASS``, ``NEURALMIND_SYNAPSE_INJECT``,
``NEURALMIND_SESSION_RECAP`` …) and fail-open guarantees, and NeuralMind does
not need to be installed in Hermes's own environment.

Which project: ``NEURALMIND_PROJECT``, else the ``project`` saved at install,
else Hermes's ``TERMINAL_CWD``, else the current directory — and only one where
``neuralmind build`` has run. Anything else, and the plugin does nothing.
Everything fails open: an error or a timeout (``NEURALMIND_HERMES_TIMEOUT``,
default 8 seconds) means no context, never a broken turn.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import threading
from pathlib import Path

CONFIG_FILENAME = "config.json"
TIMEOUT_ENV = "NEURALMIND_HERMES_TIMEOUT"
DEFAULT_TIMEOUT = 8.0

# Hermes's file-writing tools. ``patch`` also takes a V4A patch whose file
# paths sit in its text.
EDIT_TOOLS = ("write_file", "patch")
_V4A_PATH = re.compile(r"^\*\*\* (?:Update|Add) File: (.+)$", re.MULTILINE)

_HERE = Path(__file__).resolve().parent


def _config() -> dict:
    try:
        data = json.loads((_HERE / CONFIG_FILENAME).read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def _python() -> str:
    """The interpreter that has NeuralMind installed (recorded at install)."""
    python = _config().get("python")
    if isinstance(python, str) and python and Path(python).exists():
        return python
    return sys.executable


def _project() -> Path | None:
    """The NeuralMind project for this Hermes process, if it has been built."""
    candidates = (
        os.environ.get("NEURALMIND_PROJECT"),
        _config().get("project"),
        os.environ.get("TERMINAL_CWD"),
        os.getcwd(),
    )
    for candidate in candidates:
        if not candidate or not isinstance(candidate, str):
            continue
        path = Path(candidate).expanduser()
        if (path / ".neuralmind" / "build_status.json").is_file():
            return path
    return None


def _timeout() -> float:
    try:
        return float(os.environ.get(TIMEOUT_ENV, DEFAULT_TIMEOUT))
    except ValueError:
        return DEFAULT_TIMEOUT


# Hermes's launcher points PYTHONPATH at its own source and site-packages. A
# child running NeuralMind's interpreter would import those first, fail, and
# (failing open) return nothing — so the child gets a clean Python setup.
_PYTHON_ENV = ("PYTHONPATH", "PYTHONHOME", "PYTHONSAFEPATH", "PYTHONSTARTUP", "VIRTUAL_ENV")


def _child_env() -> dict:
    return {k: v for k, v in os.environ.items() if k not in _PYTHON_ENV}


def _run(action: str, payload: dict) -> str:
    """Run one NeuralMind hook action; return its additionalContext, or ""."""
    try:
        done = subprocess.run(
            [_python(), "-m", "neuralmind", "_hook", action],
            input=json.dumps(payload),
            capture_output=True,
            text=True,
            timeout=_timeout(),
            env=_child_env(),
            check=False,
        )
        if not done.stdout.strip():
            return ""
        response = json.loads(done.stdout)
        context = (response.get("hookSpecificOutput") or {}).get("additionalContext")
        return context if isinstance(context, str) else ""
    except Exception:
        return ""


def _text(user_message) -> str:
    """The text of a user message (a string, or a multimodal list of parts)."""
    if isinstance(user_message, str):
        return user_message
    if isinstance(user_message, list):
        parts = []
        for part in user_message:
            if isinstance(part, str):
                parts.append(part)
            elif isinstance(part, dict) and isinstance(part.get("text"), str):
                parts.append(part["text"])
        return "\n".join(parts)
    return ""


def on_pre_llm_call(
    session_id: str = "",
    user_message=None,
    is_first_turn: bool = False,
    parent_session_id: str = "",
    **_: object,
):
    """Return this turn's NeuralMind context for Hermes to append, or None."""
    try:
        # A subagent's "user message" was written by its parent agent; neither
        # recording it nor recalling for it is about the user's work.
        if parent_session_id or not session_id:
            return None
        project = _project()
        if project is None:
            return None
        blocks = []
        if is_first_turn:  # Hermes: no prior messages, so not a resumed session
            recap = _run(
                "session-start",
                {"cwd": str(project), "session_id": session_id, "source": "startup"},
            )
            if recap:
                blocks.append(recap)
        prompt = _text(user_message).strip()
        if prompt:
            recall = _run(
                "prompt-submit",
                {"cwd": str(project), "session_id": session_id, "prompt": prompt},
            )
            if recall:
                blocks.append(recall)
        return {"context": "\n\n".join(blocks)} if blocks else None
    except Exception:
        return None


def _edited_paths(tool_name: str, args: dict) -> list[str]:
    path = args.get("path")
    if isinstance(path, str) and path:
        return [path]
    patch = args.get("patch")
    if tool_name == "patch" and isinstance(patch, str):
        return [m.strip() for m in _V4A_PATH.findall(patch) if m.strip()]
    return []


def _failed(result) -> bool:
    """Whether a tool result reports an error (only successful edits count)."""
    if isinstance(result, str):
        try:
            result = json.loads(result)
        except ValueError:
            return False
    return isinstance(result, dict) and bool(result.get("error"))


def on_post_tool_call(
    tool_name: str = "",
    args=None,
    result=None,
    session_id: str = "",
    parent_session_id: str = "",
    **_: object,
) -> None:
    """Record a successful file edit, in the background so the turn isn't held."""
    try:
        if tool_name not in EDIT_TOOLS or not isinstance(args, dict) or not session_id:
            return
        if parent_session_id or _failed(result):
            return
        project = _project()
        if project is None:
            return
        code = args.get("content") or args.get("new_string") or args.get("patch") or ""
        payloads = []
        for path in _edited_paths(tool_name, args):
            file_path = Path(path).expanduser()
            if not file_path.is_absolute():
                file_path = project / file_path
            payloads.append(
                {
                    "cwd": str(project),
                    "session_id": session_id,
                    "tool_input": {"file_path": str(file_path), "new_string": code},
                }
            )
        if payloads:
            threading.Thread(
                target=lambda: [_run("edit-activity", p) for p in payloads], daemon=True
            ).start()
    except Exception:
        pass


def register(ctx) -> None:
    """Hermes plugin entry point."""
    ctx.register_hook("pre_llm_call", on_pre_llm_call)
    ctx.register_hook("post_tool_call", on_post_tool_call)
