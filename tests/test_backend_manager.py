"""Tests for backend factory and config loading."""

import json

import pytest

from neuralmind.backend_manager import BackendManager
from neuralmind.embedder import GraphEmbedder
from neuralmind.in_memory_backend import InMemoryEmbeddingBackend


def test_load_yaml_config(temp_project):
    cfg_path = temp_project / "neuralmind-backend.yaml"
    cfg_path.write_text("backend:\n  type: in_memory\nhybrid_context: true\n")
    manager = BackendManager(str(temp_project))
    cfg = manager.load_config()
    assert cfg["backend"]["type"] == "in_memory"
    assert cfg["hybrid_context"] is True


def test_load_json_config(temp_project):
    cfg_path = temp_project / "neuralmind-backend.json"
    cfg_path.write_text(json.dumps({"backend": {"type": "graph"}}))
    manager = BackendManager(str(temp_project))
    cfg = manager.load_config()
    assert cfg["backend"]["type"] == "graph"


def test_create_graph_backend(temp_project):
    manager = BackendManager(str(temp_project))
    backend = manager.create_backend("graph")
    assert isinstance(backend, GraphEmbedder)


def test_create_in_memory_backend(temp_project):
    manager = BackendManager(str(temp_project))
    backend = manager.create_backend("in_memory")
    assert isinstance(backend, InMemoryEmbeddingBackend)


def test_create_backend_from_config(temp_project):
    manager = BackendManager(str(temp_project))
    backend, cfg = manager.create_backend_from_config({"backend": {"type": "in_memory"}})
    assert isinstance(backend, InMemoryEmbeddingBackend)
    assert cfg["type"] == "in_memory"


def test_unsupported_backend_raises(temp_project):
    manager = BackendManager(str(temp_project))
    with pytest.raises(ValueError, match="Unsupported backend"):
        manager.create_backend("pinecone")
