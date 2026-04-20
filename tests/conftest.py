"""Pytest fixtures for NeuralMind tests."""

import json
import tempfile
from collections.abc import Generator
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest


@pytest.fixture
def sample_graph() -> dict[str, Any]:
    """Create a sample knowledge graph for testing."""
    return {
        "nodes": [
            {
                "id": "node_1",
                "name": "authenticate_user",
                "label": "authenticate_user",
                "type": "function",
                "file_type": "function",
                "file_path": "auth/handlers.py",
                "source_file": "auth/handlers.py",
                "description": "Validates user credentials and returns auth token",
                "community": 1,
            },
            {
                "id": "node_2",
                "name": "hash_password",
                "label": "hash_password",
                "type": "function",
                "file_type": "function",
                "file_path": "auth/crypto.py",
                "source_file": "auth/crypto.py",
                "description": "Securely hashes passwords using bcrypt",
                "community": 1,
            },
            {
                "id": "node_3",
                "name": "User",
                "label": "User",
                "type": "class",
                "file_type": "class",
                "file_path": "models/user.py",
                "source_file": "models/user.py",
                "description": "User model with authentication fields",
                "community": 1,
            },
            {
                "id": "node_4",
                "name": "create_task",
                "label": "create_task",
                "type": "function",
                "file_type": "function",
                "file_path": "tasks/handlers.py",
                "source_file": "tasks/handlers.py",
                "description": "Creates a new task in the database",
                "community": 2,
            },
            {
                "id": "node_5",
                "name": "Task",
                "label": "Task",
                "type": "class",
                "file_type": "class",
                "file_path": "models/task.py",
                "source_file": "models/task.py",
                "description": "Task model with status and assignment",
                "community": 2,
            },
            {
                "id": "node_6",
                "name": "api_router",
                "label": "api_router",
                "type": "function",
                "file_type": "function",
                "file_path": "api/routes.py",
                "source_file": "api/routes.py",
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
def temp_project(sample_graph: dict[str, Any]) -> Generator[Path, None, None]:
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
        readme_path.write_text("# Test Project\n\nA test project for NeuralMind unit tests.\n")

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
    records: dict[str, dict[str, Any]] = {}

    def _matches_where(metadata: dict[str, Any], where: dict[str, Any] | None) -> bool:
        if not where:
            return True
        if "$and" in where:
            return all(_matches_where(metadata, clause) for clause in where["$and"])
        for key, value in where.items():
            if metadata.get(key) != value:
                return False
        return True

    def upsert(ids, documents=None, metadatas=None, **kwargs):
        if documents is not None and len(documents) != len(ids or []):
            raise ValueError("documents length must match ids length")
        if metadatas is not None and len(metadatas) != len(ids or []):
            raise ValueError("metadatas length must match ids length")
        docs = documents or []
        metas = metadatas or []
        for i, doc_id in enumerate(ids or []):
            records[doc_id] = {
                "document": docs[i] if i < len(docs) else "",
                "metadata": metas[i] if i < len(metas) and isinstance(metas[i], dict) else {},
            }

    def get(ids=None, include=None, where=None, limit=None, **kwargs):
        selected_ids = [doc_id for doc_id in (ids or []) if doc_id in records]
        if ids is None:
            selected_ids = [
                doc_id for doc_id, rec in records.items() if _matches_where(rec["metadata"], where)
            ]
        if isinstance(limit, int) and limit >= 0:
            selected_ids = selected_ids[:limit]

        result: dict[str, Any] = {"ids": selected_ids}
        include_set = set(include or [])
        if not include or "metadatas" in include_set:
            result["metadatas"] = [records[doc_id]["metadata"] for doc_id in selected_ids]
        if not include or "documents" in include_set:
            result["documents"] = [records[doc_id]["document"] for doc_id in selected_ids]
        return result

    def count():
        return len(records)

    def delete_collection(name=None, **kwargs):
        records.clear()

    def query(query_texts, n_results=10, where=None, include=None, **kwargs):
        query_text = " ".join(query_texts or []).lower()
        include_set = set(include or [])

        candidates = [
            (doc_id, rec)
            for doc_id, rec in records.items()
            if _matches_where(rec["metadata"], where)
        ]
        scored = []
        for doc_id, rec in candidates:
            searchable = (
                f"{rec['document']} "
                f"{rec['metadata'].get('label', '')} "
                f"{rec['metadata'].get('source_file', '')}"
            ).lower()
            overlap = sum(1 for token in query_text.split() if token and token in searchable)
            distance = 1.0 / (1 + overlap)
            scored.append((distance, doc_id, rec))
        scored.sort(key=lambda item: (item[0], item[1]))
        top = scored[:n_results]

        result: dict[str, Any] = {"ids": [[doc_id for _, doc_id, _ in top]]}
        if not include or "documents" in include_set:
            result["documents"] = [[rec["document"] for _, _, rec in top]]
        if not include or "metadatas" in include_set:
            result["metadatas"] = [[rec["metadata"] for _, _, rec in top]]
        if not include or "distances" in include_set:
            result["distances"] = [[distance for distance, _, _ in top]]
        return result

    mock_collection.upsert.side_effect = upsert
    mock_collection.get.side_effect = get
    mock_collection.count.side_effect = count
    mock_collection.query.side_effect = query
    mock_client.delete_collection.side_effect = delete_collection

    mocker.patch("chromadb.PersistentClient", return_value=mock_client)

    return mock_client, mock_collection


@pytest.fixture
def mock_embedder(temp_project, sample_graph):
    """Create a mock embedder with all required attributes and methods."""
    mock = MagicMock()
    mock.project_path = temp_project
    mock.graph_path = temp_project / "graphify-out" / "graph.json"
    mock.nodes = sample_graph["nodes"]
    mock.edges = sample_graph["edges"]
    mock.graph = sample_graph

    # Mock get_stats
    mock.get_stats.return_value = {
        "total_nodes": 6,
        "communities": 3,
        "community_distribution": {1: 3, 2: 2, 3: 1},
        "db_path": str(temp_project / "graphify-out" / "neuralmind_db"),
    }

    # Mock search results
    mock.search.return_value = [
        {
            "id": "node_1",
            "document": "authenticate_user function",
            "metadata": {
                "label": "authenticate_user",
                "file_type": "function",
                "source_file": "auth/handlers.py",
                "community": 1,
            },
            "distance": 0.1,
            "score": 0.9,
        },
        {
            "id": "node_2",
            "document": "hash_password function",
            "metadata": {
                "label": "hash_password",
                "file_type": "function",
                "source_file": "auth/crypto.py",
                "community": 1,
            },
            "distance": 0.2,
            "score": 0.8,
        },
    ]

    # Mock get_community_summary
    def get_community_summary(community_id, max_nodes=20):
        nodes_in_community = [
            n for n in sample_graph["nodes"] if n.get("community") == community_id
        ]
        return {
            "community": community_id,
            "node_count": len(nodes_in_community),
            "type_summary": "functions, classes",
            "nodes": [
                {
                    "id": n["id"],
                    "label": n.get("label", n.get("name", "unknown")),
                    "file_type": n.get("file_type", "unknown"),
                    "source_file": n.get("source_file", ""),
                }
                for n in nodes_in_community[:max_nodes]
            ],
        }

    mock.get_community_summary.side_effect = get_community_summary

    return mock


@pytest.fixture
def large_graph() -> dict[str, Any]:
    """Create a larger graph for performance testing."""
    nodes = []
    edges = []
    communities = []

    # Create 100 nodes across 10 communities
    for community_id in range(1, 11):
        communities.append(
            {
                "id": community_id,
                "name": f"Module_{community_id}",
                "description": f"Module {community_id} description",
            }
        )

        for i in range(10):
            node_id = f"node_{community_id}_{i}"
            nodes.append(
                {
                    "id": node_id,
                    "name": f"function_{community_id}_{i}",
                    "label": f"function_{community_id}_{i}",
                    "type": "function",
                    "file_type": "function",
                    "file_path": f"module_{community_id}/file_{i}.py",
                    "source_file": f"module_{community_id}/file_{i}.py",
                    "description": f"Function {i} in module {community_id}",
                    "community": community_id,
                }
            )

            # Add some edges
            if i > 0:
                edges.append(
                    {
                        "source": f"node_{community_id}_{i-1}",
                        "target": node_id,
                        "type": "calls",
                    }
                )

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
