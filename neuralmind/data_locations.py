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
import subprocess
from dataclasses import asdict, dataclass
from pathlib import Path
from shlex import quote

from .state_dir import STATE_DIR_NAME

PROJECT = "project"
OUTSIDE = "outside the project"
INTEGRATION = "integrations"

# What the index backends write under a custom db_path (turbovec: store, index
# with its .stale quarantine, BM25; ChromaDB: chroma.sqlite3 and its -wal and
# -shm journals, plus one folder per collection, named by UUID).
_INDEX_PATTERNS = ("store*.sqlite*", "index*.tvim*", "bm25_index*.json", "chroma.sqlite3*")
_UUID_DIR = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}")
_HOOK_MARKER = "# neuralmind-hook-start"
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


def _file_mentions(path: Path, needle: str) -> bool:
    try:
        return needle in path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return False


def _remove_command(path: Path, *, directory: bool) -> tuple[str, Path]:
    """The command that removes ``path`` from any directory, and where its data is.

    Absolute, quoted paths. A symlink gets both removed, what it points to and
    the link: ``rm link`` leaves the data, and ``rm -rf link/`` empties a
    directory but leaves it and the link.
    """
    rm = "rm -rf" if directory else "rm"
    path = Path(os.path.abspath(path))  # absolute, without following a symlink
    if path.is_symlink():
        target = path.resolve()
        return f"{rm} {quote(str(target))} && rm {quote(str(path))}", target
    return f"{rm} {quote(str(path))}", path


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
    if target != Path(os.path.abspath(path)):
        kind = PROJECT if target.is_relative_to(root) else OUTSIDE
        detail = f"{os.path.abspath(path)} is a symlink to it"
    if note:
        remove += f"  # {note}"
    return Location(name, kind, str(target), target.exists(), holds, remove, detail)


def _records_mention(path: Path, root: Path) -> bool:
    """Whether a JSONL file has a record naming ``root`` or a path inside it.

    Each string value is compared as a path, so ``/work/app`` doesn't match a
    record for ``/work/app-old``, and parsing undoes the JSON escaping of
    backslashes and non-ASCII characters.
    """
    inside = str(root).rstrip(os.sep) + os.sep

    def strings(value):
        if isinstance(value, dict):
            for item in value.values():
                yield from strings(item)
        elif isinstance(value, list):
            for item in value:
                yield from strings(item)
        elif isinstance(value, str):
            yield value

    try:
        with path.open(encoding="utf-8", errors="replace") as file:
            for line in file:
                try:
                    record = json.loads(line)
                except ValueError:
                    continue
                if any(s == str(root) or s.startswith(inside) for s in strings(record)):
                    return True
    except OSError:
        pass
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
    locations = [
        _place(
            f"{STATE_DIR_NAME}/",
            PROJECT,
            root / STATE_DIR_NAME,
            "index, code graph, synapses, decisions, audit log, recaps, caches",
            root,
            directory=True,
        ),
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
    from .backend_manager import resolve_db_path

    db_path = resolve_db_path(root, config.get("db_path"))
    if db_path and db_path != ":memory:":
        directory = Path(db_path)
        found = sorted(
            {str(p.relative_to(directory)) for pat in _INDEX_PATTERNS for p in directory.glob(pat)}
            | {
                p.name
                for p in (directory.iterdir() if directory.is_dir() else ())
                if p.is_dir() and _UUID_DIR.fullmatch(p.name)
            }
        )
        locations.append(
            Location(
                "index at db_path",
                PROJECT if directory.resolve().is_relative_to(root) else OUTSIDE,
                str(directory),
                bool(found),
                "the vector index, including indexed text",
                (
                    " && ".join(
                        _remove_command(directory / name, directory=(directory / name).is_dir())[0]
                        for name in found
                    )
                    + f"  # then {directory} itself, if nothing else is in it"
                    if found
                    else "nothing to remove"
                ),
                ", ".join(found),
            )
        )
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
    queries = 0
    try:
        for line in log.read_text(encoding="utf-8").splitlines():
            try:
                queries += json.loads(line).get("project_path") == str(root)
            except (ValueError, AttributeError):
                continue
    except OSError:
        pass
    locations.append(
        Location(
            "global query log",
            OUTSIDE,
            str(log),
            queries > 0,
            "the text of this project's queries, among every project's",
            "remove this project's lines (DATA_DELETION.md 3.1)",
            f"{queries} line(s) from this project" if queries else "",
        )
    )

    registry = _resolve_registry_path()
    registered = False
    try:
        entries = json.loads(registry.read_text(encoding="utf-8"))
        registered = any(isinstance(e, dict) and e.get("path") == str(root) for e in entries)
    except (OSError, ValueError, TypeError):
        pass
    locations.append(
        Location(
            "project registry",
            OUTSIDE,
            str(registry),
            registered,
            "this project's path",
            f"neuralmind project remove {quote(str(root))}",
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
            team_config = load_config()
        audit_db = Path(team_config.audit_db).expanduser()
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
        team_log.present = team_log.present and _records_mention(Path(team_log.path), root)
        team_log.problem = team_problem
        if relative:
            # The writers open it as given, so each lands under its own working
            # directory; this is the one under the current directory.
            team_log.detail = (
                f"audit_db is the relative path {audit_db} in the Team config, so each "
                "process writes it under its own working directory; this is the current one's"
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


def _git_hooks_dir(root: Path) -> Path | None:
    try:
        out = subprocess.run(
            ["git", "-C", str(root), "rev-parse", "--git-path", "hooks"],
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if out.returncode != 0 or not out.stdout.strip():
        return None
    path = Path(out.stdout.strip())
    return path if path.is_absolute() else root / path


def _integrations(root: Path) -> list[Location]:
    from .hermes_install import plugin_dir

    project_settings = root / ".claude" / "settings.json"
    global_settings = Path.home() / ".claude" / "settings.json"
    locations = [
        Location(
            "Claude Code hooks",
            INTEGRATION,
            str(project_settings),
            _file_mentions(project_settings, "neuralmind _hook"),
            "hooks that write this project's data",
            f"neuralmind install-hooks {quote(str(root))} --uninstall",
        ),
        Location(
            "global Claude Code hooks",
            INTEGRATION,
            str(global_settings),
            _file_mentions(global_settings, "neuralmind _hook"),
            "hooks that write data for every project; shared",
            "neuralmind install-hooks --uninstall --global  # only if no other project uses them",
        ),
    ]
    hooks_dir = _git_hooks_dir(root)
    if hooks_dir is not None:
        blocks = sorted(
            p.name
            for p in (hooks_dir.iterdir() if hooks_dir.is_dir() else ())
            if p.is_file() and _file_mentions(p, _HOOK_MARKER)
        )
        locations.append(
            Location(
                "git hook blocks",
                INTEGRATION,
                str(hooks_dir),
                bool(blocks),
                "rebuilds that write this project's index",
                "delete each block between # neuralmind-hook-start and # neuralmind-hook-end",
                ", ".join(blocks),
            )
        )
    pin = plugin_dir() / "config.json"
    pinned = False
    try:
        pinned = json.loads(pin.read_text(encoding="utf-8")).get("project") == str(root)
    except (OSError, ValueError, AttributeError):
        pass
    locations.append(
        Location(
            "Hermes plugin pin",
            INTEGRATION,
            str(pin),
            pinned,
            "the Hermes plugin pinned to this project",
            "neuralmind install-hermes-plugin --unpin",
        )
    )
    claude_md = root / "CLAUDE.md"
    locations.append(
        Location(
            "CLAUDE.md import line",
            INTEGRATION,
            str(claude_md),
            _file_mentions(claude_md, _CLAUDE_IMPORT),
            "imports the synapse memory into every Claude Code session",
            f"delete the {_CLAUDE_IMPORT} line",
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
