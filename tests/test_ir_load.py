"""Tests for IR-as-primary-contract migration (B1).

Validates that all three backends (`GraphEmbedder`, `TurboVecEmbedder`,
`InMemoryEmbeddingBackend`) read `.neuralmind/index_ir.json` when present
and not stale, with `graphify-out/graph.json` as fallback.

Stdlib-only where possible — mostly exercises the same `_prefer_ir_over_graph`
/ `load_graph` contract the IR migration wires in. The TurboVec / ChromaDB
backends are exercised via ``InMemoryEmbeddingBackend`` (same code path,
no heavy deps); a separate non-parametrized test confirms the plumbing
holds for the concrete backends that have heavyweight dependencies.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

import pytest

from neuralmind import ir as ir_mod

# --------------------------------------------------------------------------- #
# Fixtures
# --------------------------------------------------------------------------- #


def _synthetic_graph() -> dict[str, Any]:
    """A minimal graphify-shaped graph: a file, two symbols, a doc, edges."""
    return {
        "directed": False,
        "multigraph": False,
        "graph": {},
        "built_at_commit": "abc123",
        "generated_by": "neuralmind.graphgen (tree-sitter)",
        "schema_version": 1,
        "nodes": [
            {
                "label": "app.py",
                "file_type": "code",
                "source_file": "app.py",
                "source_location": "L1",
                "id": "app_py",
                "community": 0,
                "norm_label": "app.py",
            },
            {
                "label": "handle",
                "file_type": "code",
                "source_file": "app.py",
                "source_location": "L10",
                "id": "app_py_handle",
                "community": 0,
                "norm_label": "handle",
            },
            {
                "label": "Server",
                "file_type": "code",
                "source_file": "app.py",
                "source_location": "L20",
                "id": "app_py_Server",
                "community": 0,
                "norm_label": "server",
            },
            {
                "label": "README.md",
                "file_type": "document",
                "source_file": "README.md",
                "source_location": "L1",
                "id": "readme_md",
                "community": 1,
                "norm_label": "readme.md",
            },
        ],
        "links": [
            {
                "relation": "contains",
                "context": "contains",
                "confidence": "EXTRACTED",
                "source_file": "app.py",
                "source_location": "L1",
                "weight": 1.0,
                "source": "app_py",
                "target": "app_py_handle",
                "confidence_score": 1.0,
            },
            {
                "relation": "calls",
                "context": "call",
                "confidence": "EXTRACTED",
                "source_file": "app.py",
                "source_location": "L12",
                "weight": 1.0,
                "source": "app_py_handle",
                "target": "app_py_Server",
                "confidence_score": 1.0,
            },
        ],
        "hyperedges": [],
    }


@pytest.fixture
def project_dir(tmp_path: Path) -> Path:
    """Create a minimal project directory with graphify-out/ and .neuralmind/."""
    (tmp_path / "graphify-out").mkdir(parents=True, exist_ok=True)
    (tmp_path / ".neuralmind").mkdir(parents=True, exist_ok=True)
    return tmp_path


@pytest.fixture
def in_memory_backend(project_dir: Path):
    """Create an InMemoryEmbeddingBackend for the temp project."""
    from neuralmind.in_memory_backend import InMemoryEmbeddingBackend

    return InMemoryEmbeddingBackend(str(project_dir))


# --------------------------------------------------------------------------- #
# _prefer_ir_over_graph unit tests
# --------------------------------------------------------------------------- #


class TestPreferIrOverGraph:
    """Unit tests for the mtime-comparison helper."""

    def test_ir_absent_returns_false(self, in_memory_backend, project_dir: Path):
        assert in_memory_backend._prefer_ir_over_graph() is False

    def test_ir_present_graph_absent_returns_true(self, in_memory_backend, project_dir: Path):
        ir_path = project_dir / ".neuralmind" / "index_ir.json"
        ir_path.write_text("{}", encoding="utf-8")
        assert in_memory_backend._prefer_ir_over_graph() is True

    def test_ir_newer_than_graph_returns_true(self, in_memory_backend, project_dir: Path):
        graph_path = project_dir / "graphify-out" / "graph.json"
        graph_path.write_text("{}", encoding="utf-8")
        ir_path = project_dir / ".neuralmind" / "index_ir.json"
        time.sleep(0.05)
        ir_path.write_text("{}", encoding="utf-8")
        assert in_memory_backend._prefer_ir_over_graph() is True

    def test_ir_older_than_graph_returns_false(self, in_memory_backend, project_dir: Path):
        ir_path = project_dir / ".neuralmind" / "index_ir.json"
        ir_path.write_text("{}", encoding="utf-8")
        graph_path = project_dir / "graphify-out" / "graph.json"
        time.sleep(0.05)
        graph_path.write_text("{}", encoding="utf-8")
        assert in_memory_backend._prefer_ir_over_graph() is False


# --------------------------------------------------------------------------- #
# load_graph integration tests
# --------------------------------------------------------------------------- #


class TestLoadGraphIrFirst:
    """End-to-end: load_graph reads IR when it is present and not stale."""

    def _write_ir(self, project_dir: Path, graph: dict) -> None:
        ir = ir_mod.from_graph_json(graph)
        ir_path = project_dir / ".neuralmind" / "index_ir.json"
        ir.write(ir_path)

    def _write_graph_json(self, project_dir: Path, graph: dict) -> None:
        graph_path = project_dir / "graphify-out" / "graph.json"
        graph_path.write_text(json.dumps(graph, indent=2), encoding="utf-8")

    # -- core cases --------------------------------------------------------- #

    def test_load_graph_prefers_ir_when_newer(self, in_memory_backend, project_dir: Path):
        graph = _synthetic_graph()
        self._write_graph_json(project_dir, graph)
        time.sleep(0.05)
        self._write_ir(project_dir, graph)
        assert in_memory_backend.load_graph() is True
        # IR has 4 nodes → after round-trip we get the same count
        assert len(in_memory_backend.nodes) == 4
        # Verify the data came from the IR (standard fields rebuilt)
        by_id = {n["id"]: n for n in in_memory_backend.nodes}
        assert "app_py" in by_id
        assert by_id["app_py"]["label"] == "app.py"

    def test_load_graph_uses_graph_when_newer(self, in_memory_backend, project_dir: Path):
        graph = _synthetic_graph()
        self._write_ir(project_dir, graph)
        time.sleep(0.05)
        self._write_graph_json(project_dir, graph)
        assert in_memory_backend.load_graph() is True
        # Should have read graph.json, which has 4 nodes
        assert len(in_memory_backend.nodes) == 4
        # Verify edges came through (graph.json edges key)
        assert len(in_memory_backend.edges) == 2

    def test_load_graph_falls_back_when_ir_absent(self, in_memory_backend, project_dir: Path):
        graph = _synthetic_graph()
        self._write_graph_json(project_dir, graph)
        assert in_memory_backend.load_graph() is True
        assert len(in_memory_backend.nodes) == 4
        assert len(in_memory_backend.edges) == 2

    def test_load_graph_fails_when_neither_exists(self, in_memory_backend, project_dir: Path):
        assert in_memory_backend.load_graph() is False
        assert in_memory_backend.nodes == []
        assert in_memory_backend.edges == []

    # -- error handling ----------------------------------------------------- #

    def test_load_graph_ir_malformed_falls_back(self, in_memory_backend, project_dir: Path):
        graph = _synthetic_graph()
        self._write_graph_json(project_dir, graph)
        time.sleep(0.05)
        ir_path = project_dir / ".neuralmind" / "index_ir.json"
        ir_path.write_text("not valid json {{{", encoding="utf-8")
        assert in_memory_backend.load_graph() is True
        # Fell back to graph.json
        assert len(in_memory_backend.nodes) == 4

    def test_load_graph_ir_future_version_falls_back(self, in_memory_backend, project_dir: Path):
        graph = _synthetic_graph()
        self._write_graph_json(project_dir, graph)
        time.sleep(0.05)
        # Construct a valid-looking IR with an unsupported future version
        future_ir = ir_mod.from_graph_json(graph).to_dict()
        future_ir["ir_version"] = 999
        ir_path = project_dir / ".neuralmind" / "index_ir.json"
        ir_path.write_text(json.dumps(future_ir), encoding="utf-8")
        assert in_memory_backend.load_graph() is True
        # Fell back to graph.json
        assert len(in_memory_backend.nodes) == 4

    def test_load_graph_ir_malformed_no_graph(self, in_memory_backend, project_dir: Path):
        """Malformed IR with no graph.json to fall back to → returns False."""
        ir_path = project_dir / ".neuralmind" / "index_ir.json"
        ir_path.write_text("not valid json {{{", encoding="utf-8")
        assert in_memory_backend.load_graph() is False

    # -- round-trip fidelity ------------------------------------------------ #

    def test_load_graph_round_trip_preserves_node_count(self, in_memory_backend, project_dir: Path):
        graph = _synthetic_graph()
        self._write_ir(project_dir, graph)
        assert in_memory_backend.load_graph() is True
        loaded_count = len(in_memory_backend.nodes)
        assert loaded_count == len(graph["nodes"])


# --------------------------------------------------------------------------- #
# Other backends (plumbing check — same contract, exercised directly)
# --------------------------------------------------------------------------- #


class TestOtherBackendsPlumbing:
    """Confirm ``_prefer_ir_over_graph`` works for TurboVec + GraphEmbedder."""

    def test_turbovec_backend_prefers_ir(self, tmp_path: Path):
        """TurboVecEmbedder picks up the IR when present and newer."""
        pytest.importorskip("numpy")  # TurboVec needs numpy
        from neuralmind.turbovec_backend import TurboVecEmbedder

        project_root = tmp_path / "proj"
        project_root.mkdir(parents=True, exist_ok=True)
        (project_root / "graphify-out").mkdir(parents=True, exist_ok=True)
        (project_root / ".neuralmind").mkdir(parents=True, exist_ok=True)

        backend = TurboVecEmbedder(str(project_root))
        assert backend._prefer_ir_over_graph() is False
        # After writing an IR it should prefer it
        ir = ir_mod.from_graph_json(_synthetic_graph())
        ir_path = project_root / ".neuralmind" / "index_ir.json"
        ir.write(ir_path)
        assert backend._prefer_ir_over_graph() is True

    def test_turbovec_backend_loads_ir(self, tmp_path: Path):
        """TurboVecEmbedder.load_graph reads the IR and populates nodes."""
        pytest.importorskip("numpy")
        from neuralmind.turbovec_backend import TurboVecEmbedder

        project_root = tmp_path / "proj"
        project_root.mkdir(parents=True, exist_ok=True)
        (project_root / "graphify-out").mkdir(parents=True, exist_ok=True)
        (project_root / ".neuralmind").mkdir(parents=True, exist_ok=True)

        graph = _synthetic_graph()
        ir = ir_mod.from_graph_json(graph)
        ir_path = project_root / ".neuralmind" / "index_ir.json"
        ir.write(ir_path)
        backend = TurboVecEmbedder(str(project_root))
        assert backend.load_graph() is True
        assert len(backend.nodes) == 4
        backend.close()

    def test_graph_embedder_prefers_ir(self, tmp_path: Path):
        """GraphEmbedder picks up the IR when present and newer."""
        try:
            import chromadb  # noqa: F401
        except ImportError:
            pytest.skip("chromadb not installed")
        from neuralmind.embedder import GraphEmbedder

        project_root = tmp_path / "proj"
        project_root.mkdir(parents=True, exist_ok=True)
        (project_root / "graphify-out").mkdir(parents=True, exist_ok=True)
        (project_root / ".neuralmind").mkdir(parents=True, exist_ok=True)

        backend = GraphEmbedder(str(project_root))
        assert backend._prefer_ir_over_graph() is False
        ir = ir_mod.from_graph_json(_synthetic_graph())
        ir_path = project_root / ".neuralmind" / "index_ir.json"
        ir.write(ir_path)
        assert backend._prefer_ir_over_graph() is True
