"""Backend factory and configuration loading for NeuralMind."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml

from .embedding_backend import EmbeddingBackend
from .in_memory_backend import InMemoryEmbeddingBackend

DEFAULT_BACKEND_CONFIG: dict[str, Any] = {
    # v0.22: the default is "auto" — prefer the ChromaDB-free turbovec backend
    # when its optional deps are installed, else fall back to chroma. An explicit
    # `backend:` in neuralmind-backend.yaml (or a backend= argument) always wins.
    "backend": "auto",
    "db_path": None,
    "hybrid_context": False,
    "security": {},
}

# The optional turbovec stack (the `[turbovec]` extra). All three must import for
# the turbovec backend to construct, so auto-detection gates on all of them.
_TURBOVEC_DEPS = ("turbovec", "onnxruntime", "tokenizers")


def turbovec_available() -> bool:
    """True when the optional turbovec stack (turbovec + onnxruntime + tokenizers)
    is importable, i.e. the user installed ``neuralmind[turbovec]``."""
    import importlib.util

    return all(importlib.util.find_spec(mod) is not None for mod in _TURBOVEC_DEPS)


def resolve_backend(backend: str | None) -> str:
    """Resolve the ``auto`` default (or ``None``) to a concrete backend name.

    As of v0.22 the shipped default is ``auto``: prefer turbovec when its deps
    are installed (the ChromaDB-free path), otherwise fall back to ``graph``
    (the ChromaDB-backed ``GraphEmbedder``). Any explicit, concrete backend name
    is normalised (lowercased/trimmed) and returned unchanged — so opting into
    chroma via ``backend: graph`` is always honoured.
    """
    # None, "", or a non-string (e.g. `backend: null` in YAML) all mean "auto".
    if not isinstance(backend, str) or not backend.strip():
        name = "auto"
    else:
        name = backend.strip().lower()
    if name == "auto":
        return "turbovec" if turbovec_available() else "graph"
    return name


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
    normalized = resolve_backend(backend)
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
        # Resolve "auto" (and None) to a concrete backend up front so
        # backend_name reports the real backend ("turbovec"/"graph"), not "auto".
        selected_backend = resolve_backend(backend or self.config.get("backend"))
        selected_db_path = db_path or self.config.get("db_path")
        self.backend_name = selected_backend
        self.backend = create_backend(selected_backend, self.project_path, selected_db_path)

    def switch_backend(self, backend: str, db_path: str | None = None) -> EmbeddingBackend:
        if hasattr(self.backend, "close"):
            try:
                self.backend.close()
            except Exception:
                pass
        selected_db_path = db_path or self.config.get("db_path")
        resolved = resolve_backend(backend)
        self.backend_name = resolved
        self.backend = create_backend(resolved, self.project_path, selected_db_path)
        return self.backend
