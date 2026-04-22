"""Backend factory and configuration loading for NeuralMind."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml

from .embedder import GraphEmbedder
from .embedding_backend import EmbeddingBackend
from .in_memory_backend import InMemoryEmbeddingBackend

DEFAULT_BACKEND_CONFIG: dict[str, Any] = {
    "backend": "graph",
    "db_path": None,
    "hybrid_context": False,
    "security": {},
}


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
    normalized = backend.strip().lower()
    if normalized in {"graph", "chroma", "chromadb"}:
        return GraphEmbedder(project_path, db_path=db_path)
    if normalized in {"in_memory", "inmemory", "memory"}:
        return InMemoryEmbeddingBackend(project_path, db_path=db_path)
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
        selected_backend = backend or str(self.config.get("backend", "graph"))
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
        self.backend_name = backend
        self.backend = create_backend(backend, self.project_path, selected_db_path)
        return self.backend
