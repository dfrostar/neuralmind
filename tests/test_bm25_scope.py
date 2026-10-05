"""A ``build --scope`` keeps its keyword indexes apart from the default one.

The unified BM25 index (``.neuralmind/bm25_unified_index.json``) and the
turbovec backend's docs index (``neuralmind_turbovec/bm25_index.json``) were
one file per project whatever the scope, and both were stamped with the one
``index_generation``. After ``build --scope docs`` the unified index held only
docs nodes, so a default query lost its code keyword hits; after
``build --scope code`` the docs index was deleted. Each scope now writes and
reads its own files and its own generation stamp.

Embeddings use a deterministic hashing function injected into the turbovec
backend, so nothing here needs the ONNX model.
"""

from __future__ import annotations

import hashlib
import io
import shutil
from pathlib import Path

import numpy as np
import pytest

from neuralmind import graphgen

pytest.importorskip("turbovec")
pytestmark = pytest.mark.skipif(not graphgen.is_available(), reason="tree-sitter not installed")

_FIXTURE = Path(__file__).parent / "fixtures" / "sample_project"
_DIM = 32


def _fake_embed(texts: list[str]) -> list[list[float]]:
    out = []
    for t in texts:
        vec = np.zeros(_DIM, dtype=np.float32)
        for tok in t.lower().replace("\n", " ").split():
            vec[int.from_bytes(hashlib.md5(tok.encode()).digest()[:4], "little") % _DIM] += 1.0
        out.append(vec.tolist())
    return out


def _mind(root: Path, scope: str = "all"):
    from neuralmind.core import NeuralMind

    mind = NeuralMind(str(root), backend_type="turbovec", enable_synapses=False, scope=scope)
    mind.embedder._embed_fn = _fake_embed
    mind.notice_stream = io.StringIO()
    return mind


def _build(root: Path, scope: str = "all") -> None:
    mind = _mind(root, scope)
    try:
        assert mind.build(regenerate_graph=(scope == "all"))["success"]
    finally:
        mind.close()


def _unified_ids(root: Path, scope: str = "all") -> set[str]:
    """The unified BM25 index a query of this scope reads."""
    mind = _mind(root, scope)
    try:
        mind.query("refund", learn=False)
        idx = mind.selector._unified_index()
        assert idx, "no unified BM25 index for this scope"
        return set(idx._ids)
    finally:
        mind.close()


def _is_code(node_id: str) -> bool:
    return "refund_charge" in node_id and "rationale" not in node_id


@pytest.fixture
def project(tmp_path) -> Path:
    root = tmp_path / "proj"
    shutil.copytree(_FIXTURE, root, ignore=shutil.ignore_patterns(".neuralmind"))
    _build(root)
    return root


def test_docs_scope_build_keeps_the_default_unified_index(project):
    before = _unified_ids(project)
    assert any(_is_code(i) for i in before)  # precondition

    _build(project, "docs")

    docs_ids = _unified_ids(project, "docs")
    assert docs_ids and not any(_is_code(i) for i in docs_ids)
    assert _unified_ids(project) == before

    mind = _mind(project)
    try:
        mind.query("refund", learn=False)
        hits = {h["id"] for h in mind.selector._unified_bm25_search("refund_charge", 10)}
    finally:
        mind.close()
    assert any(_is_code(i) for i in hits)


def test_code_scope_build_keeps_the_default_docs_index(project):
    mind = _mind(project)
    try:
        before = {h["id"] for h in mind.embedder.bm25_search("benchmark fixture", 10)}
    finally:
        mind.close()
    assert before  # precondition: the default backend has a docs keyword index

    _build(project, "code")

    mind = _mind(project)
    try:
        after = {h["id"] for h in mind.embedder.bm25_search("benchmark fixture", 10)}
    finally:
        mind.close()
    assert after == before
