"""paths.py — Centralized artifact path resolution for NeuralMind.

Provides a single source of truth for all artifact paths, with backward
compatibility for the legacy ``graphify-out/`` directory.

As of v4.2.0, the canonical artifact directory is ``.neuralmind/``:
  - ``.neuralmind/index_ir.json`` — canonical IR (already migrated)
  - ``.neuralmind/graph.json`` — input graph (moved from graphify-out/)
  - ``.neuralmind/neuralmind_db/`` — ChromaDB vector index
  - ``.neuralmind/neuralmind_turbovec/`` — TurboVec vector index
  - ``.neuralmind/GRAPH_REPORT.md`` — analysis report
  - ``.neuralmind/cache/`` — processing cache
  - ``.neuralmind/graph.html`` — visualization

Legacy ``graphify-out/`` paths are still read for backward compatibility,
but all new writes go to ``.neuralmind/``.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

# Canonical artifact directory name (v4.2.0+)
CANONICAL_DIR = ".neuralmind"

# Legacy artifact directory name (pre-v4.2.0)
LEGACY_DIR = "graphify-out"


def _resolve_base(project_path: str | Path) -> Path:
    """Resolve and normalize a project path, refusing path traversal."""
    base = os.path.abspath(str(project_path))
    return Path(base)


def _is_within(base: Path, target: str | Path) -> bool:
    """Check if target is within base (or equals base)."""
    try:
        Path(target).relative_to(base)
        return True
    except ValueError:
        return False


def canonical_artifact(project_path: str | Path, *parts: str) -> Path:
    """Resolve a path under the canonical ``.neuralmind/`` directory.

    This is the single choke point for all artifact path resolution.
    All new writes should use this function.
    """
    base = _resolve_base(project_path)
    target = os.path.normpath(os.path.join(base, CANONICAL_DIR, *parts))
    if not _is_within(base, target):
        raise ValueError(f"artifact path {target} escapes project root {base}")
    return Path(target)


def legacy_artifact(project_path: str | Path, *parts: str) -> Path:
    """Resolve a path under the legacy ``graphify-out/`` directory.

    Used for reading existing artifacts that haven't been migrated yet.
    """
    base = _resolve_base(project_path)
    target = os.path.normpath(os.path.join(base, LEGACY_DIR, *parts))
    if not _is_within(base, target):
        raise ValueError(f"artifact path {target} escapes project root {base}")
    return Path(target)


def graph_json_path(project_path: str | Path) -> Path:
    """Return the path to ``graph.json``, checking canonical then legacy.

    When neither exists, returns the canonical path (the default for new
    projects).
    """
    canonical = canonical_artifact(project_path, "graph.json")
    if canonical.exists():
        return canonical
    legacy = legacy_artifact(project_path, "graph.json")
    if legacy.exists():
        return legacy
    return canonical


def ir_path(project_path: str | Path) -> Path:
    """Return the path to ``index_ir.json`` (always canonical)."""
    return canonical_artifact(project_path, "index_ir.json")


def ir_meta_path(project_path: str | Path) -> Path:
    """Return the path to ``ir_meta.json`` (always canonical)."""
    return canonical_artifact(project_path, "ir_meta.json")


def vector_db_path(project_path: str | Path, backend: str = "turbovec") -> Path:
    """Return the path to the vector index directory.

    Checks canonical first, then legacy. The backend parameter selects
    the subdirectory name (``neuralmind_db`` for ChromaDB,
    ``neuralmind_turbovec`` for TurboVec).
    """
    subdir = "neuralmind_db" if backend in ("chroma", "chromadb", "graph") else "neuralmind_turbovec"
    canonical = canonical_artifact(project_path, subdir)
    if canonical.exists():
        return canonical
    return legacy_artifact(project_path, subdir)


def graph_report_path(project_path: str | Path) -> Path:
    """Return the path to ``GRAPH_REPORT.md``, checking canonical then legacy."""
    canonical = canonical_artifact(project_path, "GRAPH_REPORT.md")
    if canonical.exists():
        return canonical
    return legacy_artifact(project_path, "GRAPH_REPORT.md")


def cache_dir_path(project_path: str | Path) -> Path:
    """Return the path to the cache directory."""
    return canonical_artifact(project_path, "cache")


def graph_html_path(project_path: str | Path) -> Path:
    """Return the path to ``graph.html``, checking canonical then legacy."""
    canonical = canonical_artifact(project_path, "graph.html")
    if canonical.exists():
        return canonical
    return legacy_artifact(project_path, "graph.html")


def migrate_legacy_artifacts(project_path: str | Path) -> dict[str, Any]:
    """Migrate legacy ``graphify-out/`` artifacts to ``.neuralmind/``.

    Returns a dict with migration results:
        - ``migrated``: list of artifact names that were moved
        - ``skipped``: list of artifact names that already exist in canonical
        - ``errors``: list of (artifact, error) tuples
    """
    base = _resolve_base(project_path)
    legacy_base = base / LEGACY_DIR
    canonical_base = base / CANONICAL_DIR

    if not legacy_base.exists():
        return {"migrated": [], "skipped": [], "errors": []}

    canonical_base.mkdir(parents=True, exist_ok=True)

    migrated: list[str] = []
    skipped: list[str] = []
    errors: list[tuple[str, str]] = []

    for item in legacy_base.iterdir():
        if item.name.startswith("."):
            continue  # skip hidden files like .graphify_labels.json
        dest = canonical_base / item.name
        if dest.exists():
            skipped.append(item.name)
            continue
        try:
            item.rename(dest)
            migrated.append(item.name)
        except OSError as e:
            errors.append((item.name, str(e)))

    return {"migrated": migrated, "skipped": skipped, "errors": errors}
