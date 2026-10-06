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


class ProjectNotFoundError(FileNotFoundError):
    """A project path that does not name an existing directory."""


def require_project_dir(project_path: str | Path) -> Path:
    """Return ``project_path`` resolved, or raise :class:`ProjectNotFoundError`.

    The state stores create ``<project>/.neuralmind/`` with ``parents=True``,
    so without this check a mistyped project path silently became a new
    directory holding an empty index or decision store. Everything that opens
    project state calls it first; ``build`` and the other flows that create
    ``.neuralmind/`` inside an existing project are unaffected.
    """
    try:
        resolved = Path(project_path).resolve()
    except (ValueError, RuntimeError) as exc:
        # An embedded NUL (ValueError) or, before Python 3.13, a symlink loop
        # (RuntimeError) can't name a project either; callers handle
        # ProjectNotFoundError, not these.
        raise ProjectNotFoundError(f"project path is not valid: {project_path!r} ({exc})") from exc
    if resolved.is_dir():
        return resolved
    shown = str(project_path)
    if shown != str(resolved):
        shown = f"{shown} (resolved to {resolved})"
    problem = "is not a directory" if resolved.exists() else "does not exist"
    raise ProjectNotFoundError(f"project path {problem}: {shown}")


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


def _validated_artifact(base: Path, target: Path) -> Path:
    """Return ``target`` only if it stays within ``base``; raise otherwise.

    CodeQL recognizes this early-return guard as a taint barrier at the
    sink, unlike the conditional-raise pattern used inside
    canonical_artifact/legacy_artifact (which the analyzer cannot see
    through from graph_json_path's call sites).
    """
    try:
        target.relative_to(base)
    except ValueError:
        raise ValueError(f"artifact path {target} escapes project root {base}") from None
    return target


def graph_source_setting(project_path: str | Path) -> str:
    """The project's ``graph_source`` from ``.neuralmind.yaml`` (default ``auto``)."""
    try:
        from .neuralmind_config import NeuralmindConfig

        return NeuralmindConfig.load(_resolve_base(project_path)).graph_source
    except Exception:
        return "auto"


def graph_json_path(project_path: str | Path, graph_source: str | None = None) -> Path:
    """Return the path to ``graph.json`` for the project's ``graph_source``.

    ``auto`` (the default) checks canonical then legacy and, when neither
    exists, returns the canonical path (the default for new projects).
    ``builtin`` always returns the canonical ``.neuralmind/graph.json`` and
    ``graphify`` always returns ``graphify-out/graph.json``, whether or not
    they exist, so neither setting ever reads the other source.
    ``graph_source`` overrides the ``.neuralmind.yaml`` setting.
    """
    base = _resolve_base(project_path)
    source = graph_source or graph_source_setting(base)
    canonical = _validated_artifact(
        base, Path(os.path.normpath(os.path.join(base, CANONICAL_DIR, "graph.json")))
    )
    legacy = _validated_artifact(
        base, Path(os.path.normpath(os.path.join(base, LEGACY_DIR, "graph.json")))
    )
    if source == "builtin":
        return canonical
    if source == "graphify":
        return legacy
    if canonical.exists():
        return canonical
    if legacy.exists():
        return legacy
    return canonical


def baseline_path(project_path: str | Path) -> Path:
    """Return the path to ``baseline.json`` (always canonical)."""
    base = _resolve_base(project_path)
    return _validated_artifact(
        base, Path(os.path.normpath(os.path.join(base, CANONICAL_DIR, "baseline.json")))
    )


def ir_path(project_path: str | Path) -> Path:
    """Return the path to ``index_ir.json`` (always canonical)."""
    return canonical_artifact(project_path, "index_ir.json")


def ir_meta_path(project_path: str | Path) -> Path:
    """Return the path to ``ir_meta.json`` (always canonical)."""
    return canonical_artifact(project_path, "ir_meta.json")


def vector_db_path(project_path: str | Path, backend: str = "turbovec") -> Path:
    """Return the path to the vector index directory.

    Always returns the canonical path. Legacy fallback is removed —
    the legacy path caused index writes to graphify-out/ while doctor
    checks .neuralmind/, producing a phantom 'no nodes embedded' failure.
    """
    subdir = (
        "neuralmind_db" if backend in ("chroma", "chromadb", "graph") else "neuralmind_turbovec"
    )
    return canonical_artifact(project_path, subdir)


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
