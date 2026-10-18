"""data_locations.py — every place NeuralMind keeps data for one project.

The data deletion procedure (``docs/compliance/DATA_DELETION.md``) used to
list these locations by hand, and review kept finding ones it missed: a
``db_path`` index outside the project, the global query log, the Team audit
log, ``NEURALMIND_CONFIG_DIR``, a config named ``.yml``. Each location here is
resolved by the same helper that writes it, so the list can't drift from the
code. ``neuralmind data-locations`` prints it before and after a deletion.

Read-only: nothing here creates, changes or deletes a file.
"""

from __future__ import annotations

import json
import os
import re
import shlex
import subprocess
from collections.abc import Callable
from dataclasses import asdict, dataclass
from pathlib import Path

from .state_dir import STATE_DIR_NAME

PROJECT = "project"
OUTSIDE = "outside the project"
INTEGRATION = "integrations"

# What the index backends write under a custom db_path (turbovec: store, index
# with its .stale quarantine, BM25; ChromaDB: chroma.sqlite3 and its -wal and
# -shm journals, plus one folder per collection, named by UUID).
_INDEX_PATTERNS = ("store*.sqlite*", "index*.tvim*", "bm25_index*.json", "chroma.sqlite3*")
_UUID_DIR = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}")
_SQLITE_SUFFIXES = {".db", ".sqlite", ".sqlite3"}
_HOOK_MARKER = "# neuralmind-hook-start"
_HOOK_END = "# neuralmind-hook-end"
# How `neuralmind init-hook` names the project in its block: "." at the
# worktree root, else its path from there (shell-quoted, forward slashes).
_HOOK_TARGET = re.compile(r"\[ -f (.+?)/\.neuralmind/build_status\.json \]")
_CLAUDE_IMPORT = "@.neuralmind/SYNAPSE_MEMORY.md"


@dataclass
class Location:
    """One place that holds this project's data, or configuration that writes it."""

    name: str
    kind: str
    path: str
    present: bool
    holds: str
    remove: str
    detail: str = ""
    problem: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


def _raw_config(root: Path) -> tuple[Path | None, dict, str]:
    """The project's config file, its contents, and why it can't be read, if it can't."""
    from .backend_manager import backend_config_path, read_backend_config_file

    path = backend_config_path(root)
    if path is None:
        return None, {}, ""
    try:
        return path, read_backend_config_file(path), ""
    except Exception as exc:
        return path, {}, f"{type(exc).__name__}: {exc}"


class _UnreadableError(Exception):
    """A file exists but can't be read, so whether it holds this project's data isn't known."""


def _read(path: Path) -> str:
    """The file's text, or "" when it doesn't exist; raises ``_UnreadableError`` when it can't be read."""
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except FileNotFoundError:
        return ""
    except OSError as exc:
        raise _UnreadableError(
            f"can't be read ({exc}), so whether it holds this project's data isn't known: "
            "make it readable and run this again"
        ) from exc


def _parse_json(path: Path):
    """The file's JSON, or None when it doesn't exist; ``_UnreadableError`` when it can't be used."""
    text = _read(path)
    if not text.strip():
        return None
    try:
        return json.loads(text)
    except ValueError as exc:
        raise _UnreadableError(
            f"can't be parsed ({exc}), so whether it holds this project's data isn't known: "
            "fix it and run this again"
        ) from exc


def _present(location: Location, test: Callable[[], object]) -> Location:
    """Set whether ``location`` holds this project's data.

    A file that can't be read or parsed counts as present, with the reason as
    its problem: an inventory that drops it would look complete when it isn't.
    """
    try:
        location.present = bool(test())
    except _UnreadableError as exc:
        location.present = True
        location.problem = location.problem or str(exc)
    return location


def _file_mentions(path: Path, needle: str) -> bool:
    return needle in _read(path)


def _absolute(path: Path) -> Path:
    """``path`` made absolute as the OS reads it, without following its last part.

    The parent is resolved, so ``link/../index`` is the ``index`` beside what
    ``link`` points to, as ``open`` and ``rm`` see it (``os.path.abspath``
    would drop ``link/..`` first and name a different file). The last part is
    kept, so a symlink there can still be seen.
    """
    path = Path(path) if Path(path).is_absolute() else Path.cwd() / path
    if path.name in ("", ".", ".."):
        return path.resolve()
    return path.parent.resolve() / path.name


def _remove_command(path: Path, *, directory: bool, force: bool = False) -> tuple[str, Path]:
    """The command that removes ``path`` from any directory, and where its data is.

    Absolute, quoted paths. A symlink gets both removed, what it points to and
    the link: ``rm link`` leaves the data, and ``rm -rf link/`` empties a
    directory but leaves it and the link. What it points to is removed with
    ``-f``: another link removed first may have pointed to the same file.
    ``force`` uses ``rm -f`` on a file too, for one of several removed in turn.
    """
    rm = "rm -rf" if directory else "rm -f" if force else "rm"
    path = _absolute(path)
    if path.is_symlink():
        target = path.resolve()
        journals = ""
        if not directory and {target.suffix, path.suffix} & _SQLITE_SUFFIXES:
            # SQLite keeps a database's journals beside the file itself, not
            # beside the link, and the WAL can hold data not yet checkpointed.
            # The link's name counts too: synapses.db can point to a file
            # without a suffix.
            journals = "rm -f " + " ".join(
                shlex.quote(f"{target}{suffix}") for suffix in ("-wal", "-shm", "-journal")
            )
            journals += " && "
        rm = "rm -rf" if directory else "rm -f"
        return (
            f"{rm} {shlex.quote(str(target))} && {journals}rm {shlex.quote(str(path))}",
            target,
        )
    return f"{rm} {shlex.quote(str(path))}", path


def _place(
    name: str,
    kind: str,
    path: Path,
    holds: str,
    root: Path,
    *,
    directory: bool = False,
    note: str = "",
) -> Location:
    """A file or directory holding this project's data, and the command that removes it.

    A symlink is listed by what it points to (see ``_remove_command``).
    ``note``, a condition on removing it, follows as a shell comment.
    """
    remove, target = _remove_command(path, directory=directory)
    detail = ""
    if target != _absolute(path):
        kind = PROJECT if target.is_relative_to(root) else OUTSIDE
        detail = f"{_absolute(path)} is a symlink to it"
    if note:
        remove += f"  # {note}"
    # A link whose target is gone still counts: the link is ours to remove, and
    # a database's journals can outlive it, found only through the link.
    present = target.exists() or _absolute(path).is_symlink()
    return Location(name, kind, str(target), present, holds, remove, detail)


def _records_mention(path: Path, root: Path) -> bool:
    """Whether a JSONL file has a record naming ``root`` or a path inside it.

    Each string value is compared as a path, so ``/work/app`` doesn't match a
    record for ``/work/app-old``, and parsing undoes the JSON escaping of
    backslashes and non-ASCII characters.
    """
    # Either separator: a Windows path written with / is still inside.
    inside = tuple({str(root).rstrip("/\\") + sep for sep in (os.sep, "/")})

    def strings(value):
        if isinstance(value, dict):
            for item in value.values():
                yield from strings(item)
        elif isinstance(value, list):
            for item in value:
                yield from strings(item)
        elif isinstance(value, str):
            yield value

    malformed = 0
    for line in _read(path).splitlines():
        if not line.strip():
            continue
        try:
            record = json.loads(line)
        except ValueError:
            malformed += 1  # cut short by a crash, say: it may still be this project's
            continue
        if any(s == str(root) or s.startswith(inside) for s in strings(record)):
            return True
    if malformed:
        raise _UnreadableError(
            f"{malformed} record(s) can't be parsed, so whether they name this project "
            "isn't known: inspect them before relying on this list"
        )
    return False


def _project_locations(
    root: Path, config_path: Path | None, config: dict, config_problem: str
) -> list[Location]:
    config_file = _place(
        "config file",
        PROJECT,
        config_path or root / "neuralmind-backend.yaml",
        "configuration, including the security policy",
        root,
    )
    if config_problem:
        config_file.problem = (
            f"can't be read ({config_problem}), so a db_path index or anchored "
            "checkpoints it names aren't listed: fix the file and run this again"
        )
    state_dir = _place(
        f"{STATE_DIR_NAME}/",
        PROJECT,
        root / STATE_DIR_NAME,
        "index, code graph, synapses, decisions, audit log, recaps, caches",
        root,
        directory=True,
    )
    locations = [
        state_dir,
        _place(
            "graphify-out/",
            PROJECT,
            root / "graphify-out",
            "a legacy index or a graphify graph",
            root,
            directory=True,
        ),
        _place(
            "team memory bundle",
            PROJECT,
            root / ".neuralmind-team-memory.json",
            "learned associations; committed, so earlier versions stay in git history",
            root,
        ),
        config_file,
    ]
    # rm -rf .neuralmind/ removes a symlink inside it but not what it points to
    # (the turbovec index directory, say, moved to another disk).
    state = root / STATE_DIR_NAME

    def unlisted(exc: OSError) -> None:
        # os.walk skips a directory it can't read: say so, or the list looks complete.
        state_dir.problem = state_dir.problem or (
            f"{exc.filename} can't be listed ({exc.strerror}), so symlinks in it, and "
            "what they point to, aren't listed: make it readable and run this again"
        )

    if state.is_dir():  # a symlinked .neuralmind is walked too; links below it aren't followed
        for dirpath, dirnames, filenames in os.walk(state, onerror=unlisted):
            for name in sorted(dirnames + filenames):
                link = Path(dirpath) / name
                if link.is_symlink():
                    locations.append(
                        _place(
                            f"{link.relative_to(root)} (a symlink in {STATE_DIR_NAME}/)",
                            PROJECT,
                            link,
                            "whatever it points to, written there as part of the state directory",
                            root,
                            directory=link.is_dir(),
                        )
                    )
    from .backend_manager import resolve_db_path

    try:
        db_path = resolve_db_path(root, config.get("db_path"))
    except (TypeError, ValueError) as exc:
        db_path = None
        config_file.problem = (
            f"db_path is {config.get('db_path')!r}, not a path ({exc}), so the index it "
            "names isn't listed: fix it and run this again"
        )
    if db_path and db_path != ":memory:":
        directory = Path(db_path)
        index = Location(
            "index at db_path",
            PROJECT if directory.resolve().is_relative_to(root) else OUTSIDE,
            str(directory),
            False,
            "the vector index, including indexed text",
            "nothing to remove",
        )
        try:
            found = sorted(
                {
                    str(p.relative_to(directory))
                    for pat in _INDEX_PATTERNS
                    for p in directory.glob(pat)
                }
                | {
                    p.name
                    for p in (directory.iterdir() if directory.is_dir() else ())
                    if p.is_dir() and _UUID_DIR.fullmatch(p.name)
                }
            )
        except OSError as exc:
            index.present = True
            index.problem = (
                f"can't be listed ({exc}), so which index files it holds isn't known: "
                "make it readable and run this again"
            )
        else:
            index.present = bool(found)
            index.detail = ", ".join(found)
            if found:
                # The directory stays out of the comment: a newline in it would
                # end the comment and run the rest.
                # rm -f: a link listed before a file may have taken it already
                # (its target, or the target's journals), and a failed rm
                # would stop the rest.
                index.remove = (
                    " && ".join(
                        _remove_command(
                            directory / name, directory=(directory / name).is_dir(), force=True
                        )[0]
                        for name in found
                    )
                    + "  # then the directory itself, if nothing else is in it"
                )
        locations.append(index)
    return locations


def _outside_locations(root: Path, config: dict) -> list[Location]:
    from . import memory
    from .project_registry import _resolve_registry_path
    from .synapse_memory import CLAUDE_AUTO_FILENAME, claude_auto_memory_dir

    locations = []
    export = claude_auto_memory_dir(root) / CLAUDE_AUTO_FILENAME
    locations.append(
        _place("Claude Code synapse export", OUTSIDE, export, "code symbol and file names", root)
    )

    log = memory.global_query_events_file()
    query_log = Location(
        "global query log",
        OUTSIDE,
        str(log),
        False,
        "the text of this project's queries, among every project's",
        "remove this project's lines (DATA_DELETION.md 3.1)",
    )

    def project_queries() -> int:
        count = malformed = 0
        for line in _read(log).splitlines():
            if not line.strip():
                continue
            try:
                record = json.loads(line)
            except ValueError:
                malformed += 1  # cut short by a crash, say: it may still be this project's
                continue
            count += isinstance(record, dict) and record.get("project_path") == str(root)
        query_log.detail = f"{count} line(s) from this project" if count else ""
        if malformed:
            query_log.problem = (
                f"{malformed} line(s) can't be parsed, so whether they hold this project's "
                "queries isn't known: inspect them before relying on this list"
            )
        return count or malformed

    locations.append(_present(query_log, project_queries))

    registry = _absolute(_resolve_registry_path())
    # A relative NEURALMIND_CONFIG_DIR names another registry from another
    # directory, so the command pins the one listed here.
    pin_config = (
        f"NEURALMIND_CONFIG_DIR={shlex.quote(str(registry.parent))} "
        if os.environ.get("NEURALMIND_CONFIG_DIR")
        else ""
    )

    def registered() -> bool:
        entries = _parse_json(registry)
        return isinstance(entries, list) and any(
            isinstance(e, dict) and e.get("path") == str(root) for e in entries
        )

    locations.append(
        _present(
            Location(
                "project registry",
                OUTSIDE,
                str(registry),
                False,
                "this project's path",
                f"{pin_config}neuralmind project remove {shlex.quote(str(root))}",
            ),
            registered,
        )
    )

    security = config.get("security")
    anchor = security.get("audit_anchor_dir") if isinstance(security, dict) else None
    if isinstance(anchor, str) and anchor.strip():
        from .audit_checkpoint import anchor_checkpoints_path

        anchor_dir = Path(os.path.expanduser(anchor.strip()))
        path = anchor_checkpoints_path(
            root, anchor_dir if anchor_dir.is_absolute() else root / anchor_dir
        )
        locations.append(
            _place(
                "anchored audit checkpoints",
                OUTSIDE,
                path,
                "checkpoint record counts and hashes, no code; kept by default",
                root,
                note="only when erasure is required",
            )
        )

    team_problem = ""
    try:
        from .tier2.config import load_config

        try:
            team_config = load_config(strict=True)
        except Exception as exc:
            team_problem = (
                f"the Team config can't be read ({type(exc).__name__}: {exc}), so an "
                "audit_db it sets isn't known: fix it and run this again"
            )
            try:
                team_config = load_config()
            except Exception:
                from .tier2.config import Tier2Config

                team_config = Tier2Config()
        # As the writers open it: they don't expand ~, so neither does this, and
        # a ~/ path is reported as relative.
        audit_db = Path(team_config.audit_db)
    except Exception:
        audit_db = None
    if audit_db is not None:
        relative = not audit_db.is_absolute()
        team_log = _place(
            "Team governance audit log",
            OUTSIDE,
            audit_db,
            "this project's path and node names; hash-chained, shared by every project",
            root,
            note="the whole file only, when erasure is required",
        )
        team_log.problem = team_problem
        if team_log.present:
            _present(team_log, lambda: _records_mention(Path(team_log.path), root))
        if relative and not team_log.problem:
            # The writers open it as given, so each process writes its own copy
            # under its working directory, and only this one can be listed.
            team_log.problem = (
                f"audit_db is the relative path {audit_db} in the Team config, so each process "
                "writes its own copy under its working directory and only the current "
                "directory's is listed: set an absolute path, then find and remove the others"
            )
        locations.append(team_log)

    locations.append(
        _place(
            "~/.neuralmind/",
            OUTSIDE,
            memory.global_root(),
            "daemon files, server token, memory consent, license store; shared by every project",
            root,
            directory=True,
            note="only if no other project uses NeuralMind",
        )
    )
    return locations


def _git_hooks(root: Path) -> tuple[Path, str] | None:
    """The hooks directory, and how ``init-hook``'s block names this project.

    A monorepo's projects and a repository's worktrees share one hooks
    directory, and its block names one project, so a block counts only when
    it names this one.
    """
    try:
        out = subprocess.run(
            ["git", "-C", str(root), "rev-parse", "--show-toplevel", "--git-path", "hooks"],
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    lines = out.stdout.strip().splitlines()
    if out.returncode != 0 or len(lines) != 2:
        return None
    toplevel, hooks = Path(lines[0]), Path(lines[1])
    rel = os.path.relpath(os.path.realpath(root), os.path.realpath(toplevel))
    return (hooks if hooks.is_absolute() else root / hooks), (
        "." if rel == "." else rel.replace(os.sep, "/")
    )


def _hook_block_names(hook: Path, target: str) -> bool:
    """Whether ``hook``'s NeuralMind block rebuilds the project ``target`` names."""
    block = _read(hook).partition(_HOOK_MARKER)[2].partition(_HOOK_END)[0]
    for match in _HOOK_TARGET.finditer(block):
        try:
            if shlex.split(match.group(1)) == [target]:
                return True
        except ValueError:
            continue
    return False


def _integrations(root: Path) -> list[Location]:
    from .hermes_install import plugin_dir

    project_settings = root / ".claude" / "settings.json"
    global_settings = Path.home() / ".claude" / "settings.json"
    locations = [
        _present(
            Location(
                "Claude Code hooks",
                INTEGRATION,
                str(project_settings),
                False,
                "hooks that write this project's data",
                f"neuralmind install-hooks {shlex.quote(str(root))} --uninstall",
            ),
            lambda: _file_mentions(project_settings, "neuralmind _hook"),
        ),
        _present(
            Location(
                "global Claude Code hooks",
                INTEGRATION,
                str(global_settings),
                False,
                "hooks that write data for every project; shared",
                "neuralmind install-hooks --uninstall --global  # only if no other project uses them",
            ),
            lambda: _file_mentions(global_settings, "neuralmind _hook"),
        ),
    ]
    git = _git_hooks(root)
    if git is not None:
        hooks_dir, target = git
        hook_blocks = Location(
            "git hook blocks",
            INTEGRATION,
            str(hooks_dir),
            False,
            "rebuilds that write this project's index",
            "delete each block between # neuralmind-hook-start and # neuralmind-hook-end",
        )

        def blocks() -> list[str]:
            try:
                hooks = sorted(hooks_dir.iterdir()) if hooks_dir.is_dir() else []
            except OSError as exc:
                raise _UnreadableError(
                    f"can't be listed ({exc}), so which hooks hold a block isn't known: "
                    "make it readable and run this again"
                ) from exc
            names = sorted(p.name for p in hooks if p.is_file() and _hook_block_names(p, target))
            hook_blocks.detail = ", ".join(names)
            return names

        locations.append(_present(hook_blocks, blocks))
    pin = _absolute(plugin_dir() / "config.json")
    # A relative HERMES_HOME names another Hermes home from another directory,
    # so the command pins the one listed here.
    env_home = os.environ.get("HERMES_HOME", "").strip()
    pin_home = (
        f"HERMES_HOME={shlex.quote(str(_absolute(Path(env_home).expanduser())))} "
        if env_home
        else ""
    )

    def pinned() -> bool:
        data = _parse_json(pin)
        return isinstance(data, dict) and data.get("project") == str(root)

    locations.append(
        _present(
            Location(
                "Hermes plugin pin",
                INTEGRATION,
                str(pin),
                False,
                "the Hermes plugin pinned to this project",
                f"{pin_home}neuralmind install-hermes-plugin --unpin",
            ),
            pinned,
        )
    )
    claude_md = root / "CLAUDE.md"
    locations.append(
        _present(
            Location(
                "CLAUDE.md import line",
                INTEGRATION,
                str(claude_md),
                False,
                "imports the synapse memory into every Claude Code session",
                f"delete the {_CLAUDE_IMPORT} line",
            ),
            lambda: _file_mentions(claude_md, _CLAUDE_IMPORT),
        )
    )
    return locations


def data_locations(project_path: str | Path) -> list[Location]:
    """Every location holding this project's data, present or not."""
    root = Path(project_path).resolve()
    config_path, config, config_problem = _raw_config(root)
    return (
        _project_locations(root, config_path, config, config_problem)
        + _outside_locations(root, config)
        + _integrations(root)
    )
