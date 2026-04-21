"""Backend factory and backend configuration loading."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml

from .embedder import GraphEmbedder
from .embedding_backend import EmbeddingBackend
from .in_memory_backend import InMemoryEmbeddingBackend


class BackendManager:
    """Creates embedding backend instances from names and config."""

    def __init__(self, project_path: str, db_path: str | None = None):
        self.project_path = Path(project_path)
        self.db_path = db_path

    def load_config(self, config_path: str | None = None) -> dict[str, Any]:
        candidates = []
        if config_path:
            candidates.append(Path(config_path))
        candidates.extend(
            [
                self.project_path / "neuralmind-backend.yaml",
                self.project_path / "neuralmind-backend.yml",
                self.project_path / "neuralmind-backend.json",
            ]
        )
        for path in candidates:
            if not path.exists():
                continue
            if path.suffix.lower() == ".json":
                return json.loads(path.read_text(encoding="utf-8"))
            return yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        return {}

    def create_backend(
        self,
        backend_name: str = "graph",
        options: dict[str, Any] | None = None,
    ) -> EmbeddingBackend:
        opts = options or {}
        normalized = backend_name.lower()
        db_path = opts.get("db_path", self.db_path)

        if normalized in {"graph", "chroma", "chromadb"}:
            return GraphEmbedder(str(self.project_path), db_path=db_path)
        if normalized in {"in_memory", "memory", "mock"}:
            return InMemoryEmbeddingBackend(str(self.project_path), db_path=db_path)
        raise ValueError(f"Unsupported backend: {backend_name}")

    def create_backend_from_config(self, config: dict[str, Any]) -> tuple[EmbeddingBackend, dict[str, Any]]:
        backend_cfg = config.get("backend", {})
        backend_name = backend_cfg.get("type", "graph")
        options = backend_cfg.get("options", {})
        backend = self.create_backend(backend_name, options=options)
        return backend, backend_cfg
