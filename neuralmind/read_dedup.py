"""read_dedup.py — Deduplicate repeated reads of unchanged files.

When the agent reads the same file multiple times in a session, only the
first read needs to be full. Subsequent reads of the unchanged file are
replaced with a compact stub (lean-ctx's ctx_read dedup pattern).

This is implemented as a pre-read hook: when a file read is attempted,
we check if the file's content hash matches a cached hash. If it does,
we return a stub summary instead of the full content, saving tokens.

Design:
- Content-hash based (SHA-256) — detects any change.
- Cache stored in .neuralmind/read_cache.json.
- Max cache entries: 1,000 (LRU eviction).
- Auto-invalidate after 1 hour (staleness check).

The dedup cache is shared across the session by the SessionTracker.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import time
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# Defaults
DEFAULT_MAX_CACHE_ENTRIES = 1000
DEFAULT_MAX_AGE_SECS = 3600  # 1 hour

# Stub template for deduplicated reads
READ_STUB_TEMPLATE = """[DEDUP] File {path} read {n} times.
Content unchanged since {first_read}.
Use `read_file` for full content if needed."""


def _env_int(name: str, default: int) -> int:
    """Read an int from the environment, falling back on unset/malformed."""
    try:
        return int(os.environ[name])
    except (KeyError, ValueError):
        return default


def file_hash(path: str | Path) -> str | None:
    """Return the SHA-256 hash of a file's contents, or None if unreadable."""
    try:
        with open(path, "rb") as f:
            content = f.read()
        return hashlib.sha256(content).hexdigest()
    except Exception:
        return None


class ReadCache:
    """Track file reads and detect duplicates.

    Attributes:
        cache_dir: Directory where the JSON cache lives.
        entries: Dict mapping file path -> {hash, count, first_read, last_read}.
        max_entries: Maximum cache entries before LRU eviction.
        max_age_secs: Staleness threshold for entries.
    """

    def __init__(
        self,
        project_path: str | Path,
        max_entries: int = _env_int("NEURALMIND_MAX_READ_CACHE", DEFAULT_MAX_CACHE_ENTRIES),
        max_age_secs: int = _env_int("NEURALMIND_MAX_READ_AGE_SECS", DEFAULT_MAX_AGE_SECS),
    ):
        self.project_path = Path(project_path)
        self.cache_dir = self.project_path / ".neuralmind" / "read_cache"
        self.max_entries = max_entries
        self.max_age_secs = max_age_secs
        self.entries: dict[str, dict[str, Any]] = {}
        self._load()

    def _cache_file(self) -> Path:
        return self.cache_dir / "read_cache.json"

    def _load(self) -> None:
        """Load the cache from disk."""
        try:
            path = self._cache_file()
            if path.exists():
                self.entries = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            self.entries = {}

    def _save(self) -> None:
        """Persist the cache to disk."""
        try:
            self.cache_dir.mkdir(parents=True, exist_ok=True)
            path = self._cache_file()
            path.write_text(json.dumps(self.entries, indent=2), encoding="utf-8")
        except Exception as e:
            logger.warning("[read_dedup] failed to save cache: %s", e)

    def _evict_lru(self) -> None:
        """Evict least-recently-used entries when over capacity."""
        if len(self.entries) <= self.max_entries:
            return
        # Sort by last_read ascending
        sorted_entries = sorted(self.entries.items(), key=lambda kv: kv[1].get("last_read", 0))
        # Remove oldest 10%
        n_remove = max(1, len(sorted_entries) // 10)
        for path, _ in sorted_entries[:n_remove]:
            del self.entries[path]
        logger.debug("[read_dedup] evicted %d LRU entries", n_remove)

    def _is_stale(self, entry: dict) -> bool:
        """Check if an entry has exceeded the staleness threshold."""
        last_read = entry.get("last_read", 0)
        return (time.time() - last_read) > self.max_age_secs

    def get(self, path: str | Path) -> dict | None:
        """Check if a file has been read and its content unchanged."""
        path_key = str(path)
        entry = self.entries.get(path_key)
        if not entry:
            return None
        if self._is_stale(entry):
            del self.entries[path_key]
            return None
        current_hash = file_hash(path_key)
        if current_hash != entry.get("hash"):
            # File changed — invalidate
            del self.entries[path_key]
            return None
        # Update last_read and count
        entry["last_read"] = time.time()
        entry["count"] = entry.get("count", 1) + 1
        self._save()
        return entry

    def put(self, path: str | Path, content_hash: str | None = None) -> None:
        """Record that a file was read at this content state."""
        path_key = str(path)
        if content_hash is None:
            content_hash = file_hash(path_key)
        if content_hash is None:
            return
        self.entries[path_key] = {
            "hash": content_hash,
            "count": 1,
            "first_read": time.time(),
            "last_read": time.time(),
        }
        self._evict_lru()
        self._save()

    def clear(self) -> None:
        """Clear the entire cache."""
        self.entries = {}
        try:
            path = self._cache_file()
            if path.exists():
                path.unlink()
        except Exception:
            pass

    def stats(self) -> dict:
        """Return cache statistics."""
        total_reads = sum(e.get("count", 1) for e in self.entries.values())
        return {
            "entries": len(self.entries),
            "total_reads": total_reads,
            "max_entries": self.max_entries,
            "max_age_secs": self.max_age_secs,
        }


def get_dedup_stub(entry: dict, path: str | Path) -> str:
    """Get a deduplicated read stub for a cached file."""
    count = entry.get("count", 1)
    first_read = entry.get("first_read", 0)
    return READ_STUB_TEMPLATE.format(
        path=Path(path).name,
        n=count,
        first_read=time.strftime("%H:%M:%S", time.localtime(first_read)),
    )
