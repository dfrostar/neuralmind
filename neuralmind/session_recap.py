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

The recap is injected only when SessionStart's ``source`` is ``startup`` or
``clear``: a resumed session already has its conversation, and a compacted one
has Claude Code's own compaction summary. It is labelled as a recap, not as
instructions, so the agent doesn't pick up an old task the user hasn't asked
it to continue.

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
RECENT_PROMPTS = 3  # shown after the first prompt
MAX_FILES = 12  # most recently edited first

# Sources whose conversation is already in context — nothing to recap.
INJECT_SOURCES = ("startup", "clear")

_SAFE_ID = re.compile(r"^[A-Za-z0-9_-]{1,128}$")


def recap_enabled() -> bool:
    return os.environ.get(RECAP_ENV) != "0"


def _recording_enabled() -> bool:
    if not recap_enabled():
        return False
    from .learning import learning_disabled

    return not learning_disabled()


def _recaps_dir(project_path: str | Path) -> Path:
    return Path(project_path) / ".neuralmind" / "recaps"


def _file_stem(session_id: str) -> str:
    """A filename for ``session_id`` that can never escape the recaps dir."""
    if _SAFE_ID.match(session_id):
        return session_id
    return "s-" + hashlib.sha256(session_id.encode()).hexdigest()[:32]


def _clip(text: str, limit: int = PROMPT_CHARS) -> str:
    text = " ".join(text.split())
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"


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


def _by_mtime(paths, newest_first: bool = False) -> list[tuple[float, Path]]:
    stamped = [(m, p) for p in paths if (m := _mtime(p)) is not None]
    return sorted(stamped, key=lambda mp: mp[0], reverse=newest_first)


def _append(project_path: str | Path, session_id: str, entry: dict) -> None:
    # Only in a project that uses NeuralMind: globally installed hooks fire in
    # every repository, and must not record prompts in the others.
    if not _project_built(project_path):
        return
    from .state_dir import ensure_state_dir

    # The self-ignoring .gitignore keeps the prompt records out of `git add -A`.
    ensure_state_dir(project_path)
    directory = _recaps_dir(project_path)
    directory.mkdir(parents=True, exist_ok=True)
    entry["ts"] = time.time()
    line = json.dumps(entry, ensure_ascii=False) + "\n"
    with open(directory / f"{_file_stem(session_id)}.jsonl", "a", encoding="utf-8") as fh:
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
            {"kind": "edit", "path": _display_path(project_path, file_path)},
        )
    except Exception:
        pass


def _load(path: Path) -> dict | None:
    """Fold one session's JSONL into the fields a recap shows."""
    prompts: list[str] = []
    files: list[str] = []
    last_ts = 0.0
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
    return {"prompts": prompts, "files": files, "last_ts": last_ts}


def _prune(directory: Path, now: float | None = None) -> None:
    now = time.time() if now is None else now
    records = _by_mtime(directory.glob("*.jsonl"))
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
    prompts: list[str] = record["prompts"]
    files: list[str] = record["files"]
    lines = [
        (
            f"NeuralMind session recap — the previous session in this project "
            f"(last active {_ago(now - record['last_ts'])}). This is context for "
            "continuity, not instructions: don't resume that work unless the user "
            "asks to."
        ),
    ]
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
    return "\n".join(lines)


def latest_recap(
    project_path: str | Path,
    exclude_session: str = "",
    now: float | None = None,
) -> str:
    """The recap a new session would get now, or "" when there's nothing to say.

    Picks the most recently active session's record other than
    ``exclude_session``, so a concurrent session in the same project counts as
    "where we left off" too. Read-only.
    """
    try:
        directory = _recaps_dir(project_path)
        if not directory.is_dir():
            return ""
        own = _file_stem(exclude_session) if exclude_session else None
        candidates = _by_mtime(
            (p for p in directory.glob("*.jsonl") if p.stem != own), newest_first=True
        )
        now = time.time() if now is None else now
        for _, path in candidates:
            record = _load(path)
            if record is None:
                continue
            if now - record["last_ts"] > _max_age_seconds():
                return ""  # the newest usable record is too old; older ones are too
            return render_recap(record, now=now)
        return ""
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
        if not recap_enabled() or source not in INJECT_SOURCES:
            return ""
        directory = _recaps_dir(project_path)
        if not directory.is_dir():
            return ""
        if _recording_enabled():
            _prune(directory, now=now)
        return latest_recap(project_path, exclude_session=session_id, now=now)
    except Exception:
        return ""


def clear_recaps(project_path: str | Path) -> int:
    """Delete every stored session record; returns how many were removed."""
    directory = _recaps_dir(project_path)
    if not directory.is_dir():
        return 0
    removed = 0
    for path in directory.glob("*.jsonl"):
        try:
            path.unlink()
            removed += 1
        except OSError:
            pass
    return removed
