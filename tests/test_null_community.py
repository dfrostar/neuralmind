"""A graph node with ``"community": null`` builds like one with no community.

graphify and hand-written graphs can carry ``"community": null``. The
turbovec backend compared it with ``>= 0`` and ``int()``-ed it, so the build
failed with ``TypeError: '>=' not supported between NoneType and int``; the
IR conversion failed the same way. ``None`` now means -1, the existing
"no community" value.

Embeddings use a deterministic hashing function injected into the turbovec
backend, so nothing here needs the ONNX model.
"""

from __future__ import annotations

import hashlib
import io
import json
from pathlib import Path

import numpy as np
import pytest

from neuralmind import ir

_DIM = 32


def _fake_embed(texts: list[str]) -> list[list[float]]:
    out = []
    for t in texts:
        vec = np.zeros(_DIM, dtype=np.float32)
        for tok in t.lower().replace("\n", " ").split():
            vec[int.from_bytes(hashlib.md5(tok.encode()).digest()[:4], "little") % _DIM] += 1.0
        out.append(vec.tolist())
    return out


def _graph() -> dict:
    return {
        "nodes": [
            {
                "id": "a_fn",
                "label": "a_fn",
                "file_type": "code",
                "source_file": "a.py",
                "community": None,
            },
            {
                "id": "b_fn",
                "label": "b_fn",
                "file_type": "code",
                "source_file": "b.py",
                "community": 0,
            },
        ],
        "links": [],
    }


@pytest.mark.parametrize(
    "value, expected", [(None, -1), (3, 3), ("2", 2), (1.0, 1), ("x", -1), ([], -1)]
)
def test_node_community(value, expected):
    assert ir.node_community({"community": value}) == expected
    assert ir.node_community({}) == -1


def test_ir_conversion_reads_null_community_as_no_community():
    index_ir = ir.from_graph_json(_graph())
    clusters = {n.id: n.cluster for n in index_ir.nodes}
    assert clusters == {"a_fn": -1, "b_fn": 0}


def test_turbovec_node_helpers_accept_null_community(tmp_path):
    pytest.importorskip("turbovec")
    from neuralmind.turbovec_backend import TurboVecEmbedder

    backend = TurboVecEmbedder(str(tmp_path), embed_fn=_fake_embed)
    try:
        node = _graph()["nodes"][0]
        assert "Community" not in backend._node_to_text(node)
        assert backend._node_metadata(node)["community"] == -1
        backend.nodes = _graph()["nodes"]
        assert [n["id"] for n in backend.get_community_summary(-1)["nodes"]] == ["a_fn"]
    finally:
        backend.close()


def test_build_and_query_with_null_community(tmp_path: Path):
    pytest.importorskip("turbovec")
    from neuralmind.core import NeuralMind

    (tmp_path / "a.py").write_text("def a_fn():\n    return 1\n", encoding="utf-8")
    (tmp_path / "b.py").write_text("def b_fn():\n    return 2\n", encoding="utf-8")
    out = tmp_path / "graphify-out" / "graph.json"
    out.parent.mkdir()
    out.write_text(json.dumps(_graph()), encoding="utf-8")

    mind = NeuralMind(str(tmp_path), backend_type="turbovec", enable_synapses=False)
    mind.embedder._embed_fn = _fake_embed
    mind.notice_stream = io.StringIO()
    try:
        assert mind.build()["success"]
        assert mind.embedder.get_stats()["total_nodes"] == 2
        res = mind.query("a_fn", learn=False)
    finally:
        mind.close()
    assert "a_fn" in {h["id"] for h in res.top_search_hits}


def test_graph_data_reads_null_community_as_no_community(tmp_path):
    """The `serve` graph view built from int(None) and then sorted None with ints."""
    from types import SimpleNamespace

    from neuralmind import querying

    embedder = SimpleNamespace(
        nodes=[{"id": "a", "community": None}, {"id": "b", "community": 2}], edges=[]
    )
    mind = SimpleNamespace(embedder=embedder, synapses=None, project_path=tmp_path)
    data = querying.graph_data(mind)
    assert {n["id"]: n["community"] for n in data["nodes"]} == {"a": -1, "b": 2}


def test_in_memory_backend_reads_null_community(tmp_path):
    from neuralmind.in_memory_backend import InMemoryEmbeddingBackend

    backend = InMemoryEmbeddingBackend(str(tmp_path))
    assert backend._node_metadata({"id": "a", "community": None})["community"] == -1
    backend.nodes = [{"id": "a", "label": "a", "community": None}]
    summary = backend.get_community_summary(-1)
    assert summary["node_count"] == 1
