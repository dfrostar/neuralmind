"""Tests for backend manager and backend config loading."""

import json

from neuralmind.backend_manager import BackendManager, create_backend, load_backend_config
from neuralmind.embedder import GraphEmbedder
from neuralmind.in_memory_backend import InMemoryEmbeddingBackend


def test_backend_factory_aliases(temp_project):
    assert isinstance(create_backend("graph", str(temp_project)), GraphEmbedder)
    assert isinstance(create_backend("chroma", str(temp_project)), GraphEmbedder)
    assert isinstance(create_backend("chromadb", str(temp_project)), GraphEmbedder)
    assert isinstance(create_backend("in_memory", str(temp_project)), InMemoryEmbeddingBackend)


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
