"""Pytest fixtures for NeuralMind tests."""

import json
import os
import tempfile
from pathlib import Path
from typing import Dict, Any, Generator

import pytest


@pytest.fixture
def sample_graph() -> Dict[str, Any]:
    """Create a sample knowledge graph for testing."""
    return {
        "nodes": [
            {
                "id": "node_1",
                "name": "authenticate_user",
                "type": "function",
                "file_path": "auth/handlers.py",
                "description": "Validates user credentials and returns auth token",
                "community": 1,
            },
            {
                "id": "node_2",
                "name": "hash_password",
                "type": "function",
                "file_path": "auth/crypto.py",
                "description": "Securely hashes passwords using bcrypt",
                "community": 1,
            },
            {
                "id": "node_3",
                "name": "User",
                "type": "class",
                "file_path": "models/user.py",
                "description": "User model with authentication fields",
                "community": 1,
            },
            {
                "id": "node_4",
                "name": "create_task",
                "type": "function",
                "file_path": "tasks/handlers.py",
                "description": "Creates a new task in the database",
                "community": 2,
            },
            {
                "id": "node_5",
                "name": "Task",
                "type": "class",
                "file_path": "models/task.py",
                "description": "Task model with status and assignment",
                "community": 2,
            },
            {
                "id": "node_6",
                "name": "api_router",
                "type": "function",
                "file_path": "api/routes.py",
                "description": "Main API router with all endpoints",
                "community": 3,
            },
        ],
        "edges": [
            {"source": "node_1", "target": "node_2", "type": "calls"},
            {"source": "node_1", "target": "node_3", "type": "uses"},
            {"source": "node_4", "target": "node_5", "type": "uses"},
            {"source": "node_6", "target": "node_1", "type": "calls"},
            {"source": "node_6", "target": "node_4", "type": "calls"},
        ],
        "communities": [
            {
                "id": 1,
                "name": "Authentication",
                "description": "User authentication and security",
            },
            {
                "id": 2,
                "name": "Task Management",
                "description": "Task CRUD operations",
            },
            {
                "id": 3,
                "name": "API Layer",
                "description": "REST API endpoints and routing",
            },
        ],
    }


@pytest.fixture
def temp_project(sample_graph: Dict[str, Any]) -> Generator[Path, None, None]:
    """Create a temporary project directory with graph.json."""
    with tempfile.TemporaryDirectory() as tmpdir:
        project_path = Path(tmpdir)
        
        # Create graphify-out directory
        graphify_out = project_path / "graphify-out"
        graphify_out.mkdir(parents=True)
        
        # Write graph.json
        graph_path = graphify_out / "graph.json"
        with open(graph_path, "w") as f:
            json.dump(sample_graph, f, indent=2)
        
        # Create README.md
        readme_path = project_path / "README.md"
        readme_path.write_text(
            "# Test Project\n\n"
            "A test project for NeuralMind unit tests.\n"
        )
        
        yield project_path


@pytest.fixture
def temp_project_with_config(temp_project: Path) -> Path:
    """Create a temporary project with mempalace.yaml configuration."""
    config = {
        "project": {
            "name": "TestApp",
            "description": "A test application for unit testing NeuralMind",
            "wing": "test-app",
        }
    }
    
    config_path = temp_project / "mempalace.yaml"
    import yaml
    with open(config_path, "w") as f:
        yaml.dump(config, f)
    
    return temp_project


@pytest.fixture
def temp_project_with_claude_md(temp_project: Path) -> Path:
    """Create a temporary project with CLAUDE.md."""
    claude_md = temp_project / "CLAUDE.md"
    claude_md.write_text(
        "# TestApp\n\n"
        "This is a test application designed for AI coding assistants.\n\n"
        "## Key Features\n\n"
        "- User authentication\n"
        "- Task management\n"
        "- REST API\n"
    )
    
    return temp_project


@pytest.fixture
def empty_project() -> Generator[Path, None, None]:
    """Create an empty temporary project directory."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def mock_chromadb(mocker):
    """Mock ChromaDB for tests that don't need real embeddings."""
    mock_client = mocker.MagicMock()
    mock_collection = mocker.MagicMock()
    mock_client.get_or_create_collection.return_value = mock_collection
    
    # Mock query results
    mock_collection.query.return_value = {
        "ids": [["node_1", "node_2"]],
        "distances": [[0.1, 0.2]],
        "metadatas": [
            [
                {"name": "authenticate_user", "type": "function"},
                {"name": "hash_password", "type": "function"},
            ]
        ],
        "documents": [
            [
                "authenticate_user function Validates user credentials",
                "hash_password function Securely hashes passwords",
            ]
        ],
    }
    
    mocker.patch("chromadb.PersistentClient", return_value=mock_client)
    
    return mock_client, mock_collection


@pytest.fixture
def large_graph() -> Dict[str, Any]:
    """Create a larger graph for performance testing."""
    nodes = []
    edges = []
    communities = []
    
    # Create 100 nodes across 10 communities
    for community_id in range(1, 11):
        communities.append({
            "id": community_id,
            "name": f"Module_{community_id}",
            "description": f"Module {community_id} description",
        })
        
        for i in range(10):
            node_id = f"node_{community_id}_{i}"
            nodes.append({
                "id": node_id,
                "name": f"function_{community_id}_{i}",
                "type": "function",
                "file_path": f"module_{community_id}/file_{i}.py",
                "description": f"Function {i} in module {community_id}",
                "community": community_id,
            })
            
            # Add some edges
            if i > 0:
                edges.append({
                    "source": f"node_{community_id}_{i-1}",
                    "target": node_id,
                    "type": "calls",
                })
    
    return {
        "nodes": nodes,
        "edges": edges,
        "communities": communities,
    }


@pytest.fixture(autouse=True)
def isolate_tests(tmp_path, monkeypatch):
    """Ensure tests don't affect each other."""
    # Use temp directory for any file operations
    monkeypatch.chdir(tmp_path)
