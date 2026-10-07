"""session_recap.py — "where we left off" at the start of a new session.

A fresh agent session starts cold: the user has to re-explain what they were
doing, or ask the agent to go and find out. This module keeps a small record of
each session from fields the Claude Code hook payloads already carry, and the
next session's SessionStart hook injects a short recap of the previous one.

Recorded by hooks that are already registered (no new hook events):

- ``UserPromptSubmit`` — the prompt text, secret-redacted and truncated
- ``PostToolUse`` on Edit/Write — the edited file's path

Recording happens only in a project where ``neuralmind build`` has run (it
leaves ``.neuralmind/build_status.json``; no hook creates that file). Each
session appends to ``<project>/.neuralmind/recaps/<session_id>.jsonl``.
Appends are one short line each, so hooks running in parallel processes can't
corrupt a record the way a read-modify-write of one JSON file could. The
newest ``MAX_KEPT`` records are kept, and a record active within
``PRUNE_GRACE_SECONDS`` is never deleted, so an idle session that's still open
keeps its start.

The recap of the previous session is injected only when SessionStart's
``source`` is ``startup`` or ``clear``: a resumed session already has its
conversation. It is labelled as a recap, not as instructions, so the agent
doesn't pick up an old task the user hasn't asked it to continue.

After a compaction (``source`` is ``compact``) the session gets its *own*
record back instead. Claude Code's compaction summary is written by the model
and paraphrases: the task as the user first stated it and the exact paths of
the files already edited are what it tends to lose. The record keeps both
verbatim. ``PreCompact`` marks the session it compacts, so if the session
comes back under a new ``session_id``, the session compacted in the last
``COMPACT_WINDOW_SECONDS`` is the one recalled.

Toggles: ``NEURALMIND_SESSION_RECAP=0`` switches off recording and injection.
``NEURALMIND_NO_LEARN=1`` stops recording (nothing is written) but still
injects an existing recap. ``NEURALMIND_SESSION_RECAP_MAX_AGE_DAYS`` (default
14) drops a recap older than that.

Stdlib-only, fail-open: every public function swallows its errors.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import time
from pathlib import Path

RECAP_ENV = "NEURALMIND_SESSION_RECAP"
MAX_AGE_ENV = "NEURALMIND_SESSION_RECAP_MAX_AGE_DAYS"
DEFAULT_MAX_AGE_DAYS = 14
MAX_KEPT = 10
PRUNE_GRACE_SECONDS = 24 * 3600

# What a recap shows. The whole block stays well under a kilobyte or two so a
# session start never pays much for it.
PROMPT_CHARS = 200  # each prompt, after whitespace is collapsed
PATH_CHARS = 160  # each edited path; a longer one keeps its tail
RECENT_PROMPTS = 3  # shown after the first prompt
MAX_FILES = 12  # most recently edited first

# Sources that start without the previous session's conversation; resume
# already has it. Compact is handled on its own: it recalls this session.
INJECT_SOURCES = ("startup", "clear")
COMPACT_SOURCE = "compact"
# How recently PreCompact must have marked a session for a SessionStart that
# arrives under a different session_id to recall it.
COMPACT_WINDOW_SECONDS = 15 * 60

_SAFE_ID = re.compile(r"^[A-Za-z0-9_-]{1,128}$")
# Control characters, including line and paragraph separators: a prompt or a
# path containing one could otherwise forge extra lines in the recap.
_CONTROL = re.compile("[\x00-\x1f\x7f-\x9f\u2028\u2029]")


def recap_enabled() -> bool:
    return os.environ.get(RECAP_ENV) != "0"


def _recording_enabled() -> bool:
    if not recap_enabled():
        return False
    from .learning import learning_disabled

    return not learning_disabled()


def _recaps_dir(project_path: str | Path, create: bool = False) -> Path | None:
    """The recaps directory, or None when it's missing or not safe to use.

    A symlinked ``.neuralmind/`` or ``recaps/`` is refused: a cloned repository
    can contain either, pointing outside the project, and prompts must not be
    written there, nor ``--clear`` delete files there.
    """
    state = Path(project_path) / ".neuralmind"
    directory = state / "recaps"
    if state.is_symlink() or directory.is_symlink():
        return None
    if create:
        directory.mkdir(parents=True, exist_ok=True)
        if directory.is_symlink():  # swapped in since the check above
            return None
    return directory if directory.is_dir() else None


def _records(directory: Path) -> list[Path]:
    """The session records in ``directory``: regular files, never symlinks."""
    found = []
    for path in directory.glob("*.jsonl"):
        try:
            if not path.is_symlink() and path.is_file():
                found.append(path)
        except OSError:
            continue
    return found


def _file_stem(session_id: str) -> str:
    """A filename for ``session_id`` that can never escape the recaps dir."""
    if _SAFE_ID.match(session_id):
        return session_id
    return "s-" + hashlib.sha256(session_id.encode()).hexdigest()[:32]


def _one_line(text: str) -> str:
    return " ".join(_CONTROL.sub(" ", text).split())


def _clip(text: str, limit: int = PROMPT_CHARS) -> str:
    text = _one_line(text)
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"


def _clip_path(path: str, limit: int = PATH_CHARS) -> str:
    path = _one_line(path)
    return path if len(path) <= limit else "…" + path[-(limit - 1) :]


def _display_path(project_path: str | Path, file_path: str) -> str:
    """Project-relative when the file is inside the project, else ~-relative."""
    try:
        p = Path(file_path)
        root = Path(project_path)
        # as_posix: the recap reads the same on every OS.
        if p.is_absolute():
            try:
                return p.resolve().relative_to(root.resolve()).as_posix()
            except ValueError:
                home = Path.home()
                try:
                    return "~/" + p.relative_to(home).as_posix()
                except ValueError:
                    return p.as_posix()
        return p.as_posix()
    except Exception:
        return file_path


def _project_built(project_path: str | Path) -> bool:
    # Not just ``.neuralmind/``: the SessionStart and UserPromptSubmit hooks
    # create that directory in any repository they run in. Only a build writes
    # build_status.json.
    return (Path(project_path) / ".neuralmind" / "build_status.json").is_file()


def _mtime(path: Path) -> float | None:
    """A file's mtime, or None when it vanished (another session pruned it)."""
    try:
        return path.stat().st_mtime
    except OSError:
        return None


def _by_mtime(paths) -> list[tuple[float, Path]]:
    stamped = [(m, p) for p in paths if (m := _mtime(p)) is not None]
    return sorted(stamped, key=lambda mp: mp[0])


def _append(project_path: str | Path, session_id: str, entry: dict) -> None:
    # Only in a project that uses NeuralMind: globally installed hooks fire in
    # every repository, and must not record prompts in the others.
    if not _project_built(project_path) or (Path(project_path) / ".neuralmind").is_symlink():
        return
    from .state_dir import ensure_state_dir

    # The self-ignoring .gitignore keeps the prompt records out of `git add -A`.
    ensure_state_dir(project_path)
    directory = _recaps_dir(project_path, create=True)
    if directory is None:
        return
    target = directory / f"{_file_stem(session_id)}.jsonl"
    if target.is_symlink():
        return
    entry["ts"] = time.time()
    line = json.dumps(entry, ensure_ascii=False) + "\n"
    # O_NOFOLLOW (where the OS has it) closes the gap between the check above
    # and the open: a symlink swapped in meanwhile fails the open.
    flags = os.O_WRONLY | os.O_APPEND | os.O_CREAT | getattr(os, "O_NOFOLLOW", 0)
    with os.fdopen(os.open(target, flags, 0o600), "a", encoding="utf-8") as fh:
        fh.write(line)


def record_prompt(project_path: str | Path, session_id: str, prompt: str) -> None:
    """UserPromptSubmit: remember the prompt (redacted, truncated)."""
    try:
        if not (session_id and prompt.strip() and _recording_enabled()):
            return
        from .secret_scan import redact_text

        # Redact before truncating so a secret can't survive in the kept slice.
        scrubbed, _ = redact_text(prompt)
        _append(project_path, session_id, {"kind": "prompt", "text": _clip(scrubbed)})
    except Exception:
        pass


def record_edit(project_path: str | Path, session_id: str, file_path: str) -> None:
    """PostToolUse Edit/Write: remember which file was edited."""
    try:
        if not (session_id and file_path and _recording_enabled()):
            return
        _append(
            project_path,
            session_id,
            {"kind": "edit", "path": _clip_path(_display_path(project_path, file_path))},
        )
    except Exception:
        pass


def record_compaction(project_path: str | Path, session_id: str) -> None:
    """PreCompact: mark the session about to be compacted."""
    try:
        if not (session_id and _recording_enabled()):
            return
        _append(project_path, session_id, {"kind": "compact"})
    except Exception:
        pass


def _load(path: Path) -> dict | None:
    """Fold one session's JSONL into the fields a recap shows."""
    prompts: list[str] = []
    files: list[str] = []
    last_ts = 0.0
    compacted_ts = 0.0
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return None
    for line in lines:
        try:
            entry = json.loads(line)
            if not isinstance(entry, dict):
                continue
            ts = float(entry.get("ts") or 0)
        except (ValueError, TypeError):  # JSONDecodeError is a ValueError
            continue
        if entry.get("kind") == "compact":
            # A marker, not activity: it must not make an old session look
            # like the one the user was last working in.
            compacted_ts = max(compacted_ts, ts)
            continue
        last_ts = max(last_ts, ts)
        if entry.get("kind") == "prompt" and isinstance(entry.get("text"), str):
            prompts.append(entry["text"])
        elif entry.get("kind") == "edit" and isinstance(entry.get("path"), str):
            # Most recent edit last; an older edit of the same file moves up.
            if entry["path"] in files:
                files.remove(entry["path"])
            files.append(entry["path"])
    if not (prompts or files):
        return None
    return {"prompts": prompts, "files": files, "last_ts": last_ts, "compacted_ts": compacted_ts}


def _prune(directory: Path, now: float | None = None) -> None:
    now = time.time() if now is None else now
    records = _by_mtime(_records(directory))
    for mtime, old in records[: max(0, len(records) - MAX_KEPT)]:
        if now - mtime < PRUNE_GRACE_SECONDS:
            continue  # possibly a session that's still open
        try:
            old.unlink(missing_ok=True)
        except OSError:
            pass


def _max_age_seconds() -> float:
    try:
        days = float(os.environ.get(MAX_AGE_ENV, DEFAULT_MAX_AGE_DAYS))
    except ValueError:
        days = DEFAULT_MAX_AGE_DAYS
    return days * 86400


def _ago(seconds: float) -> str:
    minutes = int(seconds // 60)
    if minutes < 1:
        return "just now"
    if minutes < 60:
        return f"{minutes} min ago"
    hours = minutes // 60
    if hours < 48:
        return f"{hours} h ago"
    return f"{hours // 24} days ago"


def render_recap(record: dict, now: float | None = None) -> str:
    now = time.time() if now is None else now
    header = (
        f"NeuralMind session recap — the previous session in this project "
        f"(last active {_ago(now - record['last_ts'])}). This is context for "
        "continuity, not instructions: don't resume that work unless the user "
        "asks to."
    )
    return "\n".join([header, *_recap_body(record)])


def render_compaction_recap(record: dict) -> str:
    header = (
        "NeuralMind pre-compaction record — this session's own prompts (each "
        f"as written, up to {PROMPT_CHARS} characters, secrets redacted) and "
        "edited files, kept because a compaction summary can drop them. It "
        "restates what the user already asked for in this session; it adds no "
        "new instructions."
    )
    return "\n".join([header, *_recap_body(record)])


def _recap_body(record: dict) -> list[str]:
    # Clipped again here: a record may not have been written by this module.
    prompts = [_clip(p) for p in record["prompts"]]
    files = [_clip_path(f) for f in record["files"]]
    lines: list[str] = []
    if prompts:
        lines.append("")
        lines.append(f'It started with: "{prompts[0]}"')
        recent = prompts[1:][-RECENT_PROMPTS:]
        if recent:
            skipped = len(prompts) - 1 - len(recent)
            header = "Most recent prompts"
            if skipped:
                header += f" ({skipped} earlier not shown)"
            lines.append(header + ":")
            lines.extend(f'- "{p}"' for p in recent)
    if files:
        shown = list(reversed(files))[:MAX_FILES]
        more = len(files) - len(shown)
        lines.append("")
        lines.append(
            f"Files edited ({len(files)}, most recent first): "
            + ", ".join(shown)
            + (f", +{more} more" if more else "")
        )
    return lines


def latest_recap(
    project_path: str | Path,
    exclude_session: str = "",
    now: float | None = None,
) -> str:
    """The recap a new session would get now, or "" when there's nothing to say.

    Picks the record with the latest recorded activity other than
    ``exclude_session``'s, so a concurrent session in the same project counts
    as "where we left off" too. Ranked by the timestamps inside the records,
    not file mtimes: a partial append can refresh an old record's mtime without
    adding activity. Records whose last activity has the same timestamp (two
    writes inside one clock tick: about 15.6 ms on Windows) go to the one
    modified last, then by name, so the pick never depends on directory order.
    Read-only.
    """
    try:
        directory = _recaps_dir(project_path)
        if directory is None:
            return ""
        own = _file_stem(exclude_session) if exclude_session else None
        ranked = []
        for path in _records(directory):
            if path.stem == own:
                continue
            loaded = _load(path)
            if loaded is not None:
                ranked.append(((loaded["last_ts"], _mtime(path) or 0.0, path.name), loaded))
        if not ranked:
            return ""
        record = max(ranked, key=lambda item: item[0])[1]
        now = time.time() if now is None else now
        if now - record["last_ts"] > _max_age_seconds():
            return ""
        return render_recap(record, now=now)
    except Exception:
        return ""


def compaction_recap(
    project_path: str | Path,
    session_id: str,
    now: float | None = None,
) -> str:
    """This session's own record after a compaction, or "" when there is none.

    The record kept under ``session_id`` when there is one. Otherwise, in case
    the session came back from compaction under a new id, the one record
    PreCompact marked within ``COMPACT_WINDOW_SECONDS``. When two sessions
    compacted in that window, nothing links the new id to either, so there is
    no recap rather than another session's. A session that has a record file
    of its own never borrows another's, even when its own holds nothing to
    show. Read-only.
    """
    try:
        directory = _recaps_dir(project_path)
        if directory is None or not session_id:
            return ""
        own = directory / f"{_file_stem(session_id)}.jsonl"
        if own.exists():
            if own.is_symlink():
                return ""
            record = _load(own)
            return render_compaction_recap(record) if record else ""
        now = time.time() if now is None else now
        marked = []
        for path in _records(directory):
            loaded = _load(path)
            if loaded and now - loaded["compacted_ts"] <= COMPACT_WINDOW_SECONDS:
                marked.append(loaded)
        if len(marked) != 1:
            return ""
        return render_compaction_recap(marked[0])
    except Exception:
        return ""


def recap_for_session_start(
    project_path: str | Path,
    session_id: str,
    source: str,
    now: float | None = None,
) -> str:
    """The recap to inject at SessionStart, or "" when there's nothing to say."""
    try:
        if not recap_enabled():
            return ""
        if source == COMPACT_SOURCE:
            return compaction_recap(project_path, session_id, now=now)
        if source not in INJECT_SOURCES:
            return ""
        directory = _recaps_dir(project_path)
        if directory is None:
            return ""
        if _recording_enabled():
            _prune(directory, now=now)
        return latest_recap(project_path, exclude_session=session_id, now=now)
    except Exception:
        return ""


def clear_recaps(project_path: str | Path) -> int:
    """Delete every stored session record; returns how many were removed.

    Never follows a symlinked ``.neuralmind/`` or ``recaps/`` directory, and
    deletes only regular files.
    """
    directory = _recaps_dir(project_path)
    if directory is None:
        return 0
    removed = 0
    for path in _records(directory):
        try:
            path.unlink()
            removed += 1
        except OSError:
            pass
    return removed
