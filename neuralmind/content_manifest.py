"""Incremental bookkeeping for content ingestion.

`neuralmind ingest-content` used to re-parse and re-embed every file on
every run: a 1,000-chunk book cost the same ~70s whether one chapter had
changed or none had. This module records what was already embedded — the
file's SHA-256 plus the chunk parameters it was chunked with — so a
re-run only pays for files that actually changed.

Stored at ``<project>/.neuralmind/content_manifest.json``. Paths are
keyed relative to the project root where possible, so moving or cloning
the project doesn't invalidate the whole manifest.

The chunk parameters are part of the staleness check on purpose:
re-running with a different ``--chunk-size``/``--overlap`` produces
different chunk boundaries and different node ids, so those files must be
re-ingested even when their bytes are identical.

Stdlib-only, like the synapse layer — its tests run without the full
dependency set.
"""

from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

__all__ = ["ContentManifest", "MANIFEST_FILENAME", "file_digest", "manifest_path"]

MANIFEST_FILENAME = "content_manifest.json"
SCHEMA_VERSION = 1

_DIGEST_CHUNK = 1024 * 1024  # 1MB reads — bounded memory on large files


def manifest_path(project_path: str | Path) -> Path:
    """Path to a project's content manifest (may not exist yet)."""
    return Path(project_path) / ".neuralmind" / MANIFEST_FILENAME


def file_digest(path: str | Path) -> str:
    """SHA-256 of a file's bytes, streamed. Empty string if unreadable."""
    digest = hashlib.sha256()
    try:
        with open(path, "rb") as handle:
            for block in iter(lambda: handle.read(_DIGEST_CHUNK), b""):
                digest.update(block)
    except OSError:
        return ""
    return digest.hexdigest()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class ContentManifest:
    """What content ingestion has already embedded for a project.

    Args:
        root: Project root the manifest belongs to.
        entries: File key → record. Normally loaded from disk.
    """

    def __init__(self, root: str | Path, entries: dict[str, dict[str, Any]] | None = None) -> None:
        self.root = Path(root)
        self.entries: dict[str, dict[str, Any]] = entries or {}

    # -- persistence -------------------------------------------------------- #
    @classmethod
    def load(cls, project_path: str | Path) -> ContentManifest:
        """Read a project's manifest. A missing or corrupt file yields an
        empty manifest — a bad manifest costs a full re-ingest, never a crash.
        """
        root = Path(project_path)
        path = manifest_path(root)
        if not path.exists():
            return cls(root)
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError, UnicodeDecodeError):
            return cls(root)
        if not isinstance(payload, dict):
            return cls(root)
        if int(payload.get("schema_version", 0)) != SCHEMA_VERSION:
            # Forward/backward incompatible: treat everything as unindexed.
            return cls(root)
        files = payload.get("files")
        if not isinstance(files, dict):
            return cls(root)
        entries = {str(k): v for k, v in files.items() if isinstance(v, dict)}
        return cls(root, entries)

    def save(self) -> Path:
        """Write the manifest atomically. Returns the path written."""
        path = manifest_path(self.root)
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "schema_version": SCHEMA_VERSION,
            "updated_at": _now(),
            "files": self.entries,
        }
        tmp = path.with_suffix(path.suffix + ".tmp")
        tmp.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
        os.replace(tmp, path)
        return path

    # -- keys --------------------------------------------------------------- #
    def key(self, path: str | Path) -> str:
        """Stable manifest key for a file: project-relative when possible."""
        resolved = Path(path).resolve()
        try:
            return resolved.relative_to(self.root.resolve()).as_posix()
        except ValueError:
            return resolved.as_posix()

    # -- staleness ---------------------------------------------------------- #
    def is_unchanged(self, path: str | Path, *, chunk_size: int, overlap: int) -> bool:
        """True when ``path`` was embedded with these chunk params and hasn't
        changed since.

        Size is checked before the hash so the common "file grew" case
        short-circuits without reading the bytes.
        """
        entry = self.entries.get(self.key(path))
        if not entry:
            return False
        if int(entry.get("chunk_size", -1)) != int(chunk_size):
            return False
        if int(entry.get("overlap", -1)) != int(overlap):
            return False
        try:
            size = Path(path).stat().st_size
        except OSError:
            return False
        if int(entry.get("size", -1)) != int(size):
            return False
        recorded = str(entry.get("sha256", ""))
        return bool(recorded) and recorded == file_digest(path)

    # -- mutation ----------------------------------------------------------- #
    def node_ids(self, path: str | Path) -> list[str]:
        """Node ids a previous run embedded for ``path`` (empty if unknown)."""
        entry = self.entries.get(self.key(path)) or {}
        ids = entry.get("node_ids")
        return [str(i) for i in ids] if isinstance(ids, list) else []

    def record(
        self,
        path: str | Path,
        *,
        chunk_size: int,
        overlap: int,
        chunks: int,
        nodes: int,
        node_ids: list[str] | None = None,
    ) -> dict[str, Any]:
        """Mark ``path`` as embedded with these parameters.

        ``node_ids`` is what makes shrinking files safe: chunk ids are
        positional, so a file that loses its tail leaves orphaned chunks
        behind unless the caller can diff the old id set against the new.
        """
        resolved = Path(path)
        try:
            size = resolved.stat().st_size
        except OSError:
            size = -1
        entry = {
            "sha256": file_digest(resolved),
            "size": int(size),
            "chunk_size": int(chunk_size),
            "overlap": int(overlap),
            "chunks": int(chunks),
            "nodes": int(nodes),
            "node_ids": [str(i) for i in (node_ids or [])],
            "indexed_at": _now(),
        }
        self.entries[self.key(resolved)] = entry
        return entry

    def forget(self, path: str | Path) -> bool:
        """Drop a file's record. True if something was removed."""
        return self.entries.pop(self.key(path), None) is not None

    def prune_missing(self) -> tuple[list[str], list[str]]:
        """Drop records for files that no longer exist.

        Returns ``(keys, node_ids)`` — the forgotten files and every node
        id they had embedded, so the caller can evict them from the vector
        index instead of leaving a deleted chapter searchable forever.
        """
        gone: list[str] = []
        orphans: list[str] = []
        for key in list(self.entries):
            candidate = Path(key)
            if not candidate.is_absolute():
                candidate = self.root / key
            if candidate.exists():
                continue
            entry = self.entries.pop(key, None) or {}
            gone.append(key)
            ids = entry.get("node_ids")
            if isinstance(ids, list):
                orphans.extend(str(i) for i in ids)
        return gone, orphans

    # -- reporting ---------------------------------------------------------- #
    def summary(self) -> dict[str, Any]:
        """Aggregate counts for `neuralmind status` and `--json` output."""
        chunks = sum(int(e.get("chunks", 0) or 0) for e in self.entries.values())
        nodes = sum(int(e.get("nodes", 0) or 0) for e in self.entries.values())
        stamps = [str(e.get("indexed_at", "")) for e in self.entries.values()]
        stamps = [s for s in stamps if s]
        return {
            "files": len(self.entries),
            "chunks": chunks,
            "nodes": nodes,
            "last_indexed_at": max(stamps) if stamps else None,
        }

    def __len__(self) -> int:
        return len(self.entries)
