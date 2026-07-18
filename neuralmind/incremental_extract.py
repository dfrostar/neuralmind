"""
G4 — Incremental re-extraction.

Tracks file content hashes to determine which files need re-extraction on
each build. Also resolves reverse edges (importers/callers) that may need
re-extraction when a dependency changes.

Part of Wave 5 — wired into build_graph() so `neuralmind build` skips
unchanged files.

Skip-path: if no cache exists (first run, corrupted), does a full
extraction. If a file's mtime and hash are unchanged from the last
build, it's skipped.
"""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

CACHE_FILE = ".neuralmind/extraction_cache.json"
IMPORTER_INDEX_FILE = ".neuralmind/importer_index.json"


@dataclass
class FileCache:
    """Per-file cache entry for incremental extraction."""

    path: str
    mtime: float
    content_hash: str
    extracted_at: float = 0.0

    def to_dict(self) -> dict:
        return {
            "path": self.path,
            "mtime": self.mtime,
            "content_hash": self.content_hash,
            "extracted_at": self.extracted_at,
        }

    @classmethod
    def from_dict(cls, d: dict) -> FileCache:
        return cls(
            path=d["path"],
            mtime=d["mtime"],
            content_hash=d["content_hash"],
            extracted_at=d.get("extracted_at", 0.0),
        )


class IncrementalExtractor:
    """
    Tracks file content hashes to determine which files need
    re-extraction on each build. Also resolves reverse edges
    (importers/callers) that may need re-extraction when a
    dependency changes.

    Skip-path: if no cache exists (first run, corrupted), does
    a full extraction. If a file's mtime and hash are unchanged
    from the last build, it's skipped.
    """

    def __init__(self, project_path: str | Path):
        self.project_path = Path(project_path)
        self.cache_path = self.project_path / CACHE_FILE
        self._cache: dict[str, FileCache] = {}
        self._load_cache()

    def _load_cache(self) -> None:
        """Load cache from disk."""
        try:
            if self.cache_path.exists():
                data = json.loads(self.cache_path.read_text(encoding="utf-8"))
                for d in data.get("files", []):
                    fc = FileCache.from_dict(d)
                    self._cache[fc.path] = fc
        except Exception:
            self._cache = {}

    def _save_cache(self) -> None:
        """Persist cache to disk."""
        try:
            self.cache_path.parent.mkdir(parents=True, exist_ok=True)
            data = {
                "files": [fc.to_dict() for fc in self._cache.values()],
                "saved_at": time.time(),
            }
            self.cache_path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
        except Exception:
            pass  # fail-open

    def _content_hash(self, filepath: Path) -> str:
        """SHA-256 of file content. Returns empty string when unreadable."""
        if not filepath.exists():
            return ""
        try:
            return hashlib.sha256(filepath.read_bytes()).hexdigest()
        except Exception:
            return ""

    def scan_files(
        self,
        root: Path,
        suffixes: frozenset[str],
    ) -> tuple[list[str], list[str], list[str]]:
        """
        Compare current files against cache to find changes.

        Returns: (added, modified, deleted) file path lists
        """
        current_files: dict[str, float] = {}
        for f in sorted(root.rglob("*")):
            if f.is_file() and f.suffix in suffixes:
                try:
                    rel = str(f.relative_to(root))
                    parts = Path(rel).parts
                    # Skip common non-source dirs + _DEFAULT_IGNORES
                    if any(p.startswith(".") or p.startswith("__") for p in parts):
                        continue
                    # Also skip if any part is in the global ignores set
                    if any(
                        p
                        in (
                            "node_modules",
                            "graphify-out",
                            "__pycache__",
                            ".venv",
                            "venv",
                            "target",
                            "build",
                            "dist",
                        )
                        for p in parts
                    ):
                        continue
                    stat = f.stat()
                    current_files[rel] = stat.st_mtime
                except (OSError, ValueError):
                    continue

        cached_paths = set(self._cache.keys())
        current_paths = set(current_files.keys())

        added = sorted(current_paths - cached_paths)
        deleted = sorted(cached_paths - current_paths)
        modified = []

        # Check mtime + content hash for potentially-modified files
        for rel in sorted(current_paths & cached_paths):
            cached = self._cache[rel]
            if current_files.get(rel, 0) > cached.mtime:
                # mtime changed; verify with content hash
                full_path = root / rel
                new_hash = self._content_hash(full_path)
                if new_hash != cached.content_hash:
                    modified.append(rel)

        return added, modified, deleted

    def get_changed_with_dependents(
        self,
        root: Path,
        suffixes: frozenset[str],
        importer_index: dict[str, list[str]],
    ) -> list[str]:
        """
        Get changed files plus files that import them (reverse edges).

        importer_index: maps file -> list of files that import it.
        """
        added, modified, deleted = self.scan_files(root, suffixes)
        changed = set(added + modified + deleted)

        # Add importers of changed files
        to_check = list(changed)
        checked: set[str] = set()
        while to_check:
            filepath = to_check.pop(0)
            if filepath in checked:
                continue
            checked.add(filepath)
            for importer in importer_index.get(filepath, []):
                if importer not in checked and importer not in changed:
                    changed.add(importer)
                    to_check.append(importer)

        added_list = [f for f in added]
        modified_list = [f for f in modified if f not in added]
        # Importers get added to modified for re-extraction
        importer_list = [
            f for f in changed if f not in added and f not in modified and f not in deleted
        ]

        return added_list + modified_list + importer_list

    def update_cache(self, file_paths: list[str], root: Path) -> None:
        """Update cache entries for extracted files."""
        now = time.time()
        for rel in file_paths:
            full_path = root / rel
            try:
                stat = full_path.stat()
                self._cache[rel] = FileCache(
                    path=rel,
                    mtime=stat.st_mtime,
                    content_hash=self._content_hash(full_path),
                    extracted_at=now,
                )
            except (OSError, ValueError):
                continue
        self._save_cache()

    def remove_from_cache(self, file_paths: list[str]) -> None:
        """Remove deleted files from cache."""
        for p in file_paths:
            self._cache.pop(p, None)
        self._save_cache()

    def stats(self) -> dict:
        return {
            "n_cached": len(self._cache),
            "cache_file": str(self.cache_path),
        }


def build_importer_index_from_graph(graph: dict[str, Any]) -> dict[str, list[str]]:
    """Build importer_index from a graph's structural edges.

    Inverts the direction of imports_from/calls/inherits edges:
    if file A imports file B, the result maps B -> [A].

    The importer_index is the reverse-edge traversal map needed by
    get_changed_with_dependents(). It answers: "if file X changed,
    which files need re-extraction because they import/call/inherit
    from X?"
    """
    index: dict[str, list[str]] = {}

    # Build file_id -> source_file mapping
    file_nodes = [n for n in graph.get("nodes", []) if n.get("file_type") == "code"]
    file_by_id: dict[str, str] = {}
    for n in file_nodes:
        nid = n.get("id", "")
        sf = n.get("source_file", "")
        if nid == _slug(sf):  # file node id matches slug of its own path
            file_by_id[nid] = sf
        elif sf:
            file_by_id[nid] = sf

    # Invert structural edges: for each edge where target is in file B,
    # register the source's file as an importer of B
    reverse_relations = {"imports_from", "calls", "inherits", "contains"}
    for edge in graph.get("links", []):
        rel = edge.get("relation", "")
        if rel not in reverse_relations:
            continue
        target = edge.get("target", "")
        source = edge.get("source", "")
        # Find the file that owns target
        target_file = file_by_id.get(target, "")
        source_file = file_by_id.get(source, "")
        if target_file and source_file and target_file != source_file:
            if target_file not in index:
                index[target_file] = []
            if source_file not in index[target_file]:
                index[target_file].append(source_file)

    return index


def _slug(text: str) -> str:
    """Stable id fragment: collapse non-alphanumerics to single underscores."""
    import re

    _SLUG_RE = re.compile(r"[^a-zA-Z0-9]+")
    return _SLUG_RE.sub("_", text).strip("_").lower()


def save_importer_index(project_path: str | Path, index: dict[str, list[str]]) -> bool:
    """Persist importer_index to .neuralmind/ for subsequent builds.

    Returns False on any error (fail-open — never raises).
    """
    try:
        file_path = Path(project_path) / IMPORTER_INDEX_FILE
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(json.dumps(index, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        return True
    except Exception:
        return False


def load_importer_index(project_path: str | Path) -> dict[str, list[str]]:
    """Load importer_index from .neuralmind/.

    Returns empty dict when the file doesn't exist, is unreadable, or
    contains malformed JSON (fail-open).
    """
    try:
        file_path = Path(project_path) / IMPORTER_INDEX_FILE
        if not file_path.exists():
            return {}
        data = json.loads(file_path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            return {}
        # Validate: every value must be a list of strings
        return {k: v for k, v in data.items() if isinstance(v, list)}
    except Exception:
        return {}
