"""Tests for backend manager and backend config loading."""

import json

from neuralmind import backend_manager as bm
from neuralmind.backend_manager import (
    DEFAULT_BACKEND_CONFIG,
    BackendManager,
    create_backend,
    load_backend_config,
    resolve_backend,
)
from neuralmind.embedder import GraphEmbedder
from neuralmind.in_memory_backend import InMemoryEmbeddingBackend


def test_backend_factory_aliases(temp_project):
    assert isinstance(create_backend("graph", str(temp_project)), GraphEmbedder)
    assert isinstance(create_backend("chroma", str(temp_project)), GraphEmbedder)
    assert isinstance(create_backend("chromadb", str(temp_project)), GraphEmbedder)
    assert isinstance(create_backend("in_memory", str(temp_project)), InMemoryEmbeddingBackend)


def test_default_backend_is_auto():
    assert DEFAULT_BACKEND_CONFIG["backend"] == "auto"


def test_resolve_backend_explicit_passthrough():
    # Explicit, concrete names are normalised but never auto-resolved.
    assert resolve_backend("graph") == "graph"
    assert resolve_backend("Chroma") == "chroma"
    assert resolve_backend("turbovec") == "turbovec"
    assert resolve_backend("in_memory") == "in_memory"


def test_resolve_backend_auto_prefers_turbovec_when_available(monkeypatch):
    monkeypatch.setattr(bm, "turbovec_available", lambda: True)
    assert resolve_backend("auto") == "turbovec"
    assert resolve_backend(None) == "turbovec"
    assert resolve_backend("AUTO") == "turbovec"


def test_resolve_backend_auto_falls_back_to_chroma(monkeypatch):
    monkeypatch.setattr(bm, "turbovec_available", lambda: False)
    assert resolve_backend("auto") == "graph"
    assert resolve_backend(None) == "graph"
    # An explicit graph choice is honoured regardless of availability.
    assert resolve_backend("graph") == "graph"


def test_backend_manager_auto_default_falls_back_to_chroma(temp_project, monkeypatch):
    # No yaml + no explicit backend → "auto"; with turbovec absent it must
    # resolve to chroma, and backend_name reports the resolved name (not "auto").
    monkeypatch.setattr(bm, "turbovec_available", lambda: False)
    manager = BackendManager(str(temp_project))
    assert manager.backend_name == "graph"
    assert isinstance(manager.backend, GraphEmbedder)


def test_load_backend_config_yaml(temp_project):
    config_file = temp_project / "neuralmind-backend.yaml"
    config_file.write_text("backend: in_memory\nhybrid_context: true\n", encoding="utf-8")

    config = load_backend_config(temp_project)
    assert config["backend"] == "in_memory"
    assert config["hybrid_context"] is True


def test_load_backend_config_json(temp_project):
    config_file = temp_project / "neuralmind-backend.json"
    config_file.write_text(json.dumps({"backend": "graph"}), encoding="utf-8")

    config = load_backend_config(temp_project)
    assert config["backend"] == "graph"


def test_backend_manager_switches_backend(temp_project):
    manager = BackendManager(str(temp_project), backend="in_memory")
    assert isinstance(manager.backend, InMemoryEmbeddingBackend)

    manager.switch_backend("graph")
    assert isinstance(manager.backend, GraphEmbedder)
