"""Backend factory and configuration loading for NeuralMind."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml

from .embedding_backend import EmbeddingBackend
from .in_memory_backend import InMemoryEmbeddingBackend

DEFAULT_BACKEND_CONFIG: dict[str, Any] = {
    # The default is "auto" — prefer the ChromaDB-free turbovec backend when its
    # deps are importable, else fall back to chroma. Since v0.29.0 the turbovec
    # stack is a *base* dependency, so a default install resolves to turbovec
    # out of the box. An explicit `backend:` in neuralmind-backend.yaml (or a
    # backend= argument) always wins.
    "backend": "auto",
    "db_path": None,
    "hybrid_context": False,
    "security": {},
}

# The turbovec stack. All three must import for the turbovec backend to
# construct, so auto-detection gates on all of them. Base dependencies since
# v0.29.0 (previously the `[turbovec]` extra).
_TURBOVEC_DEPS = ("turbovec", "onnxruntime", "tokenizers")


def turbovec_available() -> bool:
    """True when the turbovec stack (turbovec + onnxruntime + tokenizers) is
    importable. These are base dependencies since v0.29.0, so this is normally
    True; it can be False only if a user force-uninstalled them."""
    import importlib.util

    return all(importlib.util.find_spec(mod) is not None for mod in _TURBOVEC_DEPS)


def resolve_backend(backend: str | None) -> str:
    """Resolve the ``auto`` default (or ``None``) to a concrete backend name.

    The shipped default is ``auto``: prefer turbovec when its deps are installed
    (the ChromaDB-free path — base deps since v0.29.0, so this is the normal
    default), otherwise fall back to ``graph`` (the ChromaDB-backed
    ``GraphEmbedder``, now an opt-in ``[chromadb]`` extra). Any explicit,
    concrete backend name is normalised (lowercased/trimmed) and returned
    unchanged — so opting into chroma via ``backend: graph`` is always honoured.
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
        # run without it. See issue #204. As of v0.29.0 ChromaDB is an opt-in
        # extra, so a missing import means the user selected the chroma backend
        # without installing it — surface an actionable hint, not a raw
        # ModuleNotFoundError from deep in the import.
        try:
            from .embedder import GraphEmbedder
        except ModuleNotFoundError as exc:
            if exc.name and exc.name.split(".")[0] == "chromadb":
                raise ModuleNotFoundError(
                    "the 'graph' (ChromaDB) backend needs ChromaDB, which is no "
                    "longer installed by default. Install it with "
                    '`pip install "neuralmind[chromadb]"`, or use the default '
                    "ChromaDB-free turbovec backend (remove `backend: graph` "
                    "from neuralmind-backend.yaml).",
                    name=exc.name,
                ) from exc
            raise

        return GraphEmbedder(project_path, db_path=db_path)
    if normalized in {"in_memory", "inmemory", "memory"}:
        return InMemoryEmbeddingBackend(project_path, db_path=db_path)
    if normalized in {"turbovec", "turboquant"}:
        # Lazy import, mirroring the chroma branch — keeps construction symmetric
        # and import-light. turbovec is the default backend since v0.29.0.
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
