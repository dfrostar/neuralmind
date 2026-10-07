"""NeuralMind for Hermes-Agent — code memory injected into each turn, no tool call.

A Hermes plugin (``~/.hermes/plugins/neuralmind/``), installed and enabled by
``neuralmind install-hermes-plugin``, or by Hermes from a clone of this
directory. It gives Hermes what NeuralMind's Claude Code hooks give Claude Code:

- ``pre_llm_call`` (once per turn, before the model runs): the files and
  decisions related to the user's message, from NeuralMind's synapse layer,
  returned as ``{"context": ...}`` so Hermes appends them to that turn's user
  message. On a session's first turn, the session recap of the previous
  session in the project comes first.
- ``post_tool_call`` on ``write_file`` and ``patch``: the edited file is
  recorded, for the next session's recap and for the synapse layer.

It is a thin, stdlib-only shim. Each action runs ``neuralmind _hook <action>``
with the same JSON payload Claude Code sends, so Hermes gets the same behavior,
toggles (``NEURALMIND_BYPASS``, ``NEURALMIND_SYNAPSE_INJECT``,
``NEURALMIND_SESSION_RECAP`` …) and fail-open guarantees, and NeuralMind does
not need to be installed in Hermes's own environment. Which NeuralMind: the
Python interpreter ``install-hermes-plugin`` recorded, else the ``neuralmind``
command on PATH, else Hermes's own Python.

Which project: ``NEURALMIND_PROJECT``, else the ``project`` saved at install,
else Hermes's ``TERMINAL_CWD`` (or, only when that's unset, the current
directory) — and only one where ``neuralmind build`` has run. Anything else,
and the plugin does nothing.
Everything fails open: an error or a timeout (``NEURALMIND_HERMES_TIMEOUT``,
default 8 seconds) means no context, never a broken turn. When NeuralMind can't
be run, is too old or times out, the plugin says so once per process in
Hermes's log (``hermes logs --level WARNING``).
"""

from __future__ import annotations

import json
import logging
import os
import re
import subprocess
import sys
import threading
from pathlib import Path

logger = logging.getLogger(__name__)

CONFIG_FILENAME = "config.json"
TIMEOUT_ENV = "NEURALMIND_HERMES_TIMEOUT"
DEFAULT_TIMEOUT = 8.0

# Hermes's file-writing tools. ``patch`` also takes a V4A patch whose file
# paths sit in its text.
EDIT_TOOLS = ("write_file", "patch")
_V4A_PATH = re.compile(r"^\*\*\* (?:Update|Add) File: (.+)$", re.MULTILINE)
# Files a V4A patch removes: deleted ones, and the source side of a move.
_V4A_GONE = re.compile(r"^\*\*\* (?:Delete File: (.+)|Move File: (.+?) ->)", re.MULTILINE)

_HERE = Path(__file__).resolve().parent

# Turns that aren't the user's work: a subagent's (its "user message" is written by
# the parent agent) and a cron job's. Hermes's post_tool_call carries neither
# parent_session_id nor platform, so their edits are recognised by what their
# pre_llm_call (which runs first) reported: the session id, and the task id,
# which survives Hermes rotating the session id mid-run. Insertion-ordered dicts
# used as bounded sets: the oldest ids are evicted first.
_SUBAGENT_SESSIONS: dict[str, None] = {}
_SUBAGENT_TASKS: dict[str, None] = {}
_SUBAGENT_SESSIONS_MAX = 4096
NON_USER_PLATFORMS = ("cron",)


def _remember(ids: dict, key: str) -> None:
    if not key:
        return
    ids.pop(key, None)
    ids[key] = None
    while len(ids) > _SUBAGENT_SESSIONS_MAX:
        ids.pop(next(iter(ids)))


def _config() -> dict:
    try:
        data = json.loads((_HERE / CONFIG_FILENAME).read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def _python() -> str | None:
    """The interpreter that has NeuralMind installed, if the installer recorded one."""
    python = _config().get("python")
    if isinstance(python, str) and python and Path(python).exists():
        return python
    return None


def _on_path(name: str = "neuralmind") -> str | None:
    """The ``name`` command on PATH, looked up in absolute PATH entries only.

    ``shutil.which`` also searches the working directory (on Windows, first),
    where a served repository could put a ``neuralmind`` of its own.
    """
    suffixes = (".exe",) if sys.platform == "win32" else ("",)
    for entry in os.environ.get("PATH", "").split(os.pathsep):
        if not entry or not os.path.isabs(entry):
            continue
        for suffix in suffixes:
            candidate = os.path.join(entry, name + suffix)
            if os.path.isfile(candidate) and os.access(candidate, os.X_OK):
                return candidate
    return None


def _command(action: str) -> list[str]:
    """The command that runs one NeuralMind hook action.

    The interpreter ``install-hermes-plugin`` recorded; else, as for a plugin
    Hermes installed from a clone, the ``neuralmind`` command on PATH; else
    Hermes's own Python, in case NeuralMind is installed alongside Hermes.
    """
    python = _python()
    if python:
        return [python, "-m", "neuralmind", "_hook", action]
    script = _on_path()
    if script:
        return [script, "_hook", action]
    return [sys.executable, "-m", "neuralmind", "_hook", action]


_WARNED: set[str] = set()

MIN_NEURALMIND = (4, 9)
_INSTALL_HINT = (
    "Install NeuralMind 4.9 or later so the `neuralmind` command is on Hermes's PATH, "
    "or run `neuralmind install-hermes-plugin` to point the plugin at it."
)
_version_checked = False


def _warn_once(kind: str, message: str, *args: object) -> None:
    """Log one warning per kind and process; the plugin itself still fails open."""
    if kind not in _WARNED:
        _WARNED.add(kind)
        logger.warning("NeuralMind plugin: " + message, *args)


def _check_version(prefix: list[str]) -> None:
    """Warn if the NeuralMind found is too old: an old one still answers, without a recap."""
    try:
        done = subprocess.run(
            [*prefix, "--version"],
            capture_output=True,
            text=True,
            timeout=_timeout(),
            env=_child_env(),
            cwd=str(_HERE),
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            check=False,
        )
        found = re.search(r"(\d+)\.(\d+)\.\d+", done.stdout)
        if found and (int(found.group(1)), int(found.group(2))) < MIN_NEURALMIND:
            _warn_once(
                "version",
                "%s is NeuralMind %s, too old for this plugin: turns get no session recap. %s",
                prefix[0],
                found.group(0),
                _INSTALL_HINT,
            )
    except Exception:
        pass


def _project() -> Path | None:
    """The NeuralMind project for this Hermes process, if it has been built."""
    terminal_cwd = os.environ.get("TERMINAL_CWD")
    candidates = (
        os.environ.get("NEURALMIND_PROJECT"),
        _config().get("project"),
        terminal_cwd,
        # Hermes works in TERMINAL_CWD when it's set, so an unbuilt TERMINAL_CWD
        # means no project — not the directory the process happened to start in.
        None if terminal_cwd else os.getcwd(),
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
# child running NeuralMind's interpreter (or its `neuralmind` script) would
# import those first, fail, and (failing open) return nothing — so the child
# gets a clean Python setup.
_PYTHON_ENV = ("PYTHONPATH", "PYTHONHOME", "PYTHONSAFEPATH", "PYTHONSTARTUP", "VIRTUAL_ENV")


def _child_env() -> dict:
    env = {k: v for k, v in os.environ.items() if k not in _PYTHON_ENV}
    # `python -m` puts the working directory first on sys.path: a served
    # repository with its own neuralmind/ or neuralmind.py would run instead of
    # the installed package. PYTHONSAFEPATH (3.11+) drops that entry; the child
    # also runs from the plugin's own directory, which holds no such module.
    env["PYTHONSAFEPATH"] = "1"
    return env


def _run(action: str, payload: dict) -> str:
    """Run one NeuralMind hook action; return its additionalContext, or ""."""
    global _version_checked
    try:
        command = _command(action)
        if not _version_checked:  # once per process, off the turn's path
            _version_checked = True
            try:
                threading.Thread(target=_check_version, args=(command[:-2],), daemon=True).start()
            except Exception:  # e.g. no thread to spare: skip the diagnostic, not the hook
                pass
        try:
            done = subprocess.run(
                command,
                input=json.dumps(payload),
                capture_output=True,
                text=True,
                timeout=_timeout(),
                env=_child_env(),
                cwd=str(_HERE),
                # Windows: no console window flashing up when Hermes runs windowless.
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                check=False,
            )
        except subprocess.TimeoutExpired:
            _warn_once(
                "timeout",
                "`neuralmind _hook %s` took longer than %ss and was stopped, so its result "
                "was left out. Set %s higher if this keeps happening.",
                action,
                _timeout(),
                TIMEOUT_ENV,
            )
            return ""
        except OSError as exc:
            _warn_once("start", "couldn't run %s (%s). %s", command[0], exc, _INSTALL_HINT)
            return ""
        # `neuralmind _hook` exits 0 whatever happens inside it, so any other
        # status means NeuralMind itself didn't start: not installed, or too old.
        if done.returncode != 0:
            detail = (done.stderr or "").strip().splitlines()
            _warn_once(
                "exit",
                "`%s` exited with status %s (%s). %s",
                " ".join(command),
                done.returncode,
                detail[-1] if detail else "no output",
                _INSTALL_HINT,
            )
            return ""
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
    task_id: str = "",
    platform: str = "",
    **_: object,
):
    """Return this turn's NeuralMind context for Hermes to append, or None."""
    try:
        # A subagent's "user message" was written by its parent agent, and a cron
        # job's by a schedule; neither is about the user's work, so neither is
        # recorded or answered with recall.
        if parent_session_id or platform in NON_USER_PLATFORMS:
            _remember(_SUBAGENT_SESSIONS, session_id)
            _remember(_SUBAGENT_TASKS, task_id)
            return None
        if not session_id:
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


def _result_dict(result) -> dict:
    if isinstance(result, str):
        try:
            result = json.loads(result)
        except ValueError:
            return {}
    return result if isinstance(result, dict) else {}


def _v4a_added(patch: str) -> dict:
    """Each file's added lines in a V4A patch, keyed by its (normalised) path."""
    sections: dict = {}
    current = None
    for line in patch.splitlines():
        header = re.match(r"^\*\*\* (?:Update|Add) File: (.+)$", line)
        move = re.match(r"^\*\*\* Move File: .+? -> (.+)$", line)
        if header or move:
            current = _norm((header or move).group(1))
            sections.setdefault(current, [])
        elif line.startswith("*** "):
            current = None  # Delete File, End Patch …
        elif current is not None and line.startswith("+"):
            sections[current].append(line[1:])
    return {path: "\n".join(added) for path, added in sections.items()}


def _edited_paths(tool_name: str, args: dict) -> list[str]:
    path = args.get("path")
    if isinstance(path, str) and path:
        return [path]
    patch = args.get("patch")
    if tool_name == "patch" and isinstance(patch, str):
        return [m.strip() for m in _V4A_PATH.findall(patch) if m.strip()]
    return []


def _norm(path: str) -> str:
    path = path.strip().replace("\\", "/")
    while path.startswith("./"):
        path = path[2:]
    return path.lstrip("/")


def _matches_any(path: str, suffixes: set) -> bool:
    """Whether ``path`` is, or ends in whole components with, one of ``suffixes``."""
    path = _norm(path)
    return any(path == s or path.endswith("/" + s) for s in suffixes)


def _code_for(file_path: Path, per_file: dict) -> str:
    for section, added in per_file.items():
        if section and _matches_any(str(file_path), {section}):
            return added
    return ""  # still recorded for the recap; no reuse feedback without its code


def _failed(result, status=None) -> bool:
    """Whether the tool call didn't land (only successful edits count).

    Hermes reports "ok", or "error", "cancelled", "timeout" … (with a plain-text
    result). Only "ok", or no status when Hermes didn't supply one, counts as
    landed — and not a patch Hermes reports changed nothing (``no_change``).
    """
    reported = _result_dict(result)
    return (
        status not in (None, "", "ok")
        or bool(reported.get("error"))
        or bool(reported.get("no_change"))
    )


def on_post_tool_call(
    tool_name: str = "",
    args=None,
    result=None,
    session_id: str = "",
    status=None,
    parent_session_id: str = "",
    task_id: str = "",
    **_: object,
) -> None:
    """Record a successful file edit, in the background so the turn isn't held."""
    try:
        if tool_name not in EDIT_TOOLS or not isinstance(args, dict) or not session_id:
            return
        if parent_session_id or session_id in _SUBAGENT_SESSIONS:
            return
        if (task_id and task_id in _SUBAGENT_TASKS) or _failed(result, status):
            return
        project = _project()
        if project is None:
            return
        patch_text = args.get("patch")
        # A V4A patch spans several files: each file gets only its own added
        # lines, so reuse feedback doesn't tie one file to another's code.
        per_file = _v4a_added(patch_text) if isinstance(patch_text, str) else None
        code = args.get("content") or args.get("new_string") or ""
        # Hermes reports the absolute paths it wrote (files_modified). Without
        # them, resolve as Hermes does: against TERMINAL_CWD, else its own
        # working directory — not against a pinned project.
        reported = _result_dict(result)
        written = reported.get("files_modified")
        if isinstance(written, list) and written and all(isinstance(p, str) for p in written):
            deleted = reported.get("files_deleted")
            gone = [p for p in deleted if isinstance(p, str)] if isinstance(deleted, list) else []
            if isinstance(patch_text, str):
                gone += [(d or m).strip() for d, m in _V4A_GONE.findall(patch_text) if (d or m)]
            # files_deleted and the patch headers may spell a path differently
            # (raw header vs the resolved path), so match on whole path components.
            suffixes = {_norm(g) for g in gone if _norm(g)}
            paths = [p for p in written if not _matches_any(p, suffixes)]
        else:
            paths = _edited_paths(tool_name, args)
        base = Path(os.environ.get("TERMINAL_CWD") or os.getcwd())
        payloads = []
        for path in paths:
            file_path = Path(path).expanduser()
            if not file_path.is_absolute():
                file_path = base / file_path
            payloads.append(
                {
                    "cwd": str(project),
                    "session_id": session_id,
                    "tool_input": {
                        "file_path": str(file_path),
                        "new_string": _code_for(file_path, per_file) if per_file else code,
                    },
                }
            )
        if payloads:
            # Not a daemon: Python waits for it at exit, so a short-lived Hermes run
            # (`hermes chat -q`) doesn't drop the edits it just made. Each call is
            # bounded by the timeout.
            threading.Thread(
                target=lambda: [_run("edit-activity", p) for p in payloads], daemon=False
            ).start()
    except Exception:
        pass


def register(ctx) -> None:
    """Hermes plugin entry point."""
    ctx.register_hook("pre_llm_call", on_pre_llm_call)
    ctx.register_hook("post_tool_call", on_post_tool_call)
