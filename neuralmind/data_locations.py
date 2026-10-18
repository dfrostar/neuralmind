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

from .state_dir import STATE_DIR_NAME

PROJECT = "project"
OUTSIDE = "outside the project"
INTEGRATION = "integrations"

# What the index backends write under a custom db_path (turbovec: store, index
# with its .stale quarantine, BM25; ChromaDB: chroma.sqlite3 plus one folder
# per collection, named by UUID).
_INDEX_PATTERNS = ("store*.sqlite*", "index*.tvim*", "bm25_index*.json", "chroma.sqlite3")
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

    def to_dict(self) -> dict:
        return asdict(self)


def _raw_config(root: Path) -> tuple[Path | None, dict]:
    """The project's config file and its contents, tolerating a broken file."""
    from .backend_manager import backend_config_path, read_backend_config_file

    path = backend_config_path(root)
    if path is None:
        return None, {}
    try:
        data = read_backend_config_file(path)
    except Exception:
        return path, {}
    return path, data if isinstance(data, dict) else {}


def _file_mentions(path: Path, needle: str) -> bool:
    try:
        return needle in path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return False


def _project_locations(root: Path, config_path: Path | None, config: dict) -> list[Location]:
    locations = [
        Location(
            ".neuralmind/",
            PROJECT,
            str(root / STATE_DIR_NAME),
            (root / STATE_DIR_NAME).exists(),
            "index, code graph, synapses, decisions, audit log, recaps, caches",
            "rm -rf .neuralmind/",
        ),
        Location(
            "graphify-out/",
            PROJECT,
            str(root / "graphify-out"),
            (root / "graphify-out").exists(),
            "a legacy index or a graphify graph",
            "rm -rf graphify-out/",
        ),
        Location(
            "team memory bundle",
            PROJECT,
            str(root / ".neuralmind-team-memory.json"),
            (root / ".neuralmind-team-memory.json").exists(),
            "learned associations; committed, so earlier versions stay in git history",
            "rm .neuralmind-team-memory.json",
        ),
        Location(
            "config file",
            PROJECT,
            str(config_path or root / "neuralmind-backend.yaml"),
            config_path is not None,
            "configuration, including the security policy",
            f"rm {config_path.name if config_path else 'neuralmind-backend.yaml'}",
        ),
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
                PROJECT if directory.is_relative_to(root) else OUTSIDE,
                str(directory),
                bool(found),
                "the vector index, including indexed text",
                "delete the files listed; the directory only if nothing else is in it",
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
        Location(
            "Claude Code synapse export",
            OUTSIDE,
            str(export),
            export.exists(),
            "code symbol and file names",
            f"rm {export}",
        )
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
            f"neuralmind project remove {root}",
        )
    )

    security = config.get("security") if isinstance(config.get("security"), dict) else {}
    anchor = security.get("audit_anchor_dir")
    if isinstance(anchor, str) and anchor.strip():
        from .audit_checkpoint import anchor_checkpoints_path

        anchor_dir = Path(os.path.expanduser(anchor.strip()))
        path = anchor_checkpoints_path(
            root, anchor_dir if anchor_dir.is_absolute() else root / anchor_dir
        )
        locations.append(
            Location(
                "anchored audit checkpoints",
                OUTSIDE,
                str(path),
                path.exists(),
                "checkpoint record counts and hashes, no code; kept by default",
                f"rm {path} (only when erasure is required)",
            )
        )

    try:
        from .tier2.config import load_config

        audit_db = Path(load_config().audit_db).expanduser()
    except Exception:
        audit_db = None
    if audit_db is not None:
        locations.append(
            Location(
                "Team governance audit log",
                OUTSIDE,
                str(audit_db),
                audit_db.exists() and _file_mentions(audit_db, str(root)),
                "this project's path and node names; hash-chained, shared by every project",
                f"rm {audit_db} (whole file only, when erasure is required)",
            )
        )

    shared = memory.global_root()
    locations.append(
        Location(
            "~/.neuralmind/",
            OUTSIDE,
            str(shared),
            shared.exists(),
            "daemon files, server token, memory consent, license store; shared by every project",
            f"rm -rf {shared} (only if no other project uses NeuralMind)",
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
            "neuralmind install-hooks --uninstall",
        ),
        Location(
            "global Claude Code hooks",
            INTEGRATION,
            str(global_settings),
            _file_mentions(global_settings, "neuralmind _hook"),
            "hooks that write data for every project; shared",
            "neuralmind install-hooks --uninstall --global (if no other project uses them)",
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
    config_path, config = _raw_config(root)
    return (
        _project_locations(root, config_path, config)
        + _outside_locations(root, config)
        + _integrations(root)
    )
