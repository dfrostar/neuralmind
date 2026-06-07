"""Backend factory and configuration loading for NeuralMind."""

from __future__ import annotations

import importlib.util
import json
import logging
from pathlib import Path
from typing import Any

import yaml

from .embedding_backend import EmbeddingBackend
from .in_memory_backend import InMemoryEmbeddingBackend

logger = logging.getLogger("neuralmind")

# "auto" (the default since v0.22.0) resolves to the ChromaDB-free turbovec
# backend when its deps are importable, otherwise the chroma backend. A bare
# `pip install neuralmind` has no turbovec, so it stays on chroma — nothing
# changes until you `pip install neuralmind[turbovec]`. An explicit `backend:`
# in neuralmind-backend.yaml always wins.
DEFAULT_BACKEND_CONFIG: dict[str, Any] = {
    "backend": "auto",
    "db_path": None,
    "hybrid_context": False,
    "security": {},
}


def _turbovec_available() -> bool:
    """True when every dep the turbovec backend needs is importable."""
    return all(
        importlib.util.find_spec(m) is not None
        for m in ("turbovec", "onnxruntime", "tokenizers", "numpy")
    )


def resolve_backend_name(backend: str) -> str:
    """Map a (possibly ``auto``) backend name to a concrete backend."""
    normalized = backend.strip().lower()
    if normalized == "auto":
        return "turbovec" if _turbovec_available() else "graph"
    return normalized


def load_backend_config(project_path: str | Path) -> dict[str, Any]:
    root = Path(project_path).resolve()
    candidates = (
        root / "neuralmind-backend.yaml",
        root / "neuralmind-backend.yml",
        root / "neuralmind-backend.json",
    )

    loaded: dict[str, Any] = {}
    for path in candidates:
        if not path.exists():
            continue
        try:
            if path.suffix in {".yaml", ".yml"}:
                with path.open(encoding="utf-8") as file:
                    parsed = yaml.safe_load(file) or {}
            else:
                with path.open(encoding="utf-8") as file:
                    parsed = json.load(file) or {}
            if isinstance(parsed, dict):
                loaded = parsed
            break
        except Exception:
            loaded = {}
            break

    config = DEFAULT_BACKEND_CONFIG.copy()
    config.update(loaded)
    return config


def create_backend(
    backend: str,
    project_path: str,
    db_path: str | None = None,
) -> EmbeddingBackend:
    normalized = resolve_backend_name(backend)
    if normalized in {"graph", "chroma", "chromadb"}:
        # Lazy import: keeps ChromaDB (a heavy tree) off the import path unless
        # the chroma backend is actually selected, so the turbovec backend can
        # run without it. See issue #204.
        from .embedder import GraphEmbedder

        return GraphEmbedder(project_path, db_path=db_path)
    if normalized in {"in_memory", "inmemory", "memory"}:
        return InMemoryEmbeddingBackend(project_path, db_path=db_path)
    if normalized in {"turbovec", "turboquant"}:
        # Lazy import: keeps the optional turbovec dependency out of the import
        # path for the default (chroma) backend. POC — see issue #204.
        from .turbovec_backend import TurboVecEmbedder

        return TurboVecEmbedder(project_path, db_path=db_path)
    raise ValueError(f"Unsupported backend: {backend}")


def _auto_migration_notice(project_path: str, resolved: str) -> None:
    """One-time heads-up when auto-selection lands on a backend whose on-disk
    index doesn't exist yet but another backend's does. The index rebuilds
    automatically on first use (``_ensure_built``); this just explains why."""
    out = Path(project_path) / "graphify-out"
    chroma_idx = out / "neuralmind_db"
    turbovec_idx = out / "neuralmind_turbovec"
    if resolved == "turbovec" and chroma_idx.exists() and not turbovec_idx.exists():
        logger.info(
            "Auto-selected the ChromaDB-free 'turbovec' backend; your existing "
            "chroma index will be rebuilt on first use. Pin `backend: graph` in "
            "neuralmind-backend.yaml to keep using the chroma index."
        )


class BackendManager:
    """Coordinates backend selection and runtime backend switching."""

    def __init__(
        self,
        project_path: str,
        db_path: str | None = None,
        backend: str | None = None,
    ):
        self.project_path = str(Path(project_path).resolve())
        self.config = load_backend_config(self.project_path)
        selected_backend = backend or str(self.config.get("backend", "auto"))
        selected_db_path = db_path or self.config.get("db_path")
        # backend_name is the *resolved* concrete backend (so "auto" reports as
        # "turbovec"/"graph"); requested_backend remembers whether it was auto.
        self.requested_backend = selected_backend
        self.backend_name = resolve_backend_name(selected_backend)
        if selected_backend.strip().lower() == "auto":
            _auto_migration_notice(self.project_path, self.backend_name)
        self.backend = create_backend(selected_backend, self.project_path, selected_db_path)

    def switch_backend(self, backend: str, db_path: str | None = None) -> EmbeddingBackend:
        if hasattr(self.backend, "close"):
            try:
                self.backend.close()
            except Exception:
                pass
        selected_db_path = db_path or self.config.get("db_path")
        self.requested_backend = backend
        self.backend_name = resolve_backend_name(backend)
        self.backend = create_backend(backend, self.project_path, selected_db_path)
        return self.backend
