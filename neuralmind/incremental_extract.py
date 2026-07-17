"""
G4 — Incremental re-extraction.

Currently only re-embedding is incremental. On each build,
re-extract symbols from changed files + their callers/importers
(reverse edges already indexed in structural_edges). Skip
full-tree reparse for large repos.

Requires G3 (modularity tracking), structural_edges (done).
"""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

CACHE_FILE = ".neuralmind/extraction_cache.json"


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
    def from_dict(cls, d: dict) -> "FileCache":
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
            self.cache_path.write_text(
                json.dumps(data, indent=2) + "\n", encoding="utf-8"
            )
        except Exception:
            pass  # fail-open

    def _content_hash(self, filepath: Path) -> str:
        """SHA-256 of file content."""
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
                    # Skip common non-source dirs
                    if any(p.startswith(".") or p.startswith("__") for p in Path(rel).parts):
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
        importer_list = [f for f in changed if f not in added and f not in modified and f not in deleted]
        
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
