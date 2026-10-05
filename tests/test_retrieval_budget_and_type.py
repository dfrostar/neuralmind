"""``query_type`` and ``context_budget`` do what ``NeuralMind.query`` documents.

* ``query_type='code'|'docs'`` (``neuralmind query --type``) ranks L3 with
  the requested intent instead of the detected one. It used to re-boost the
  already-boosted hits with the *detected* intent after the context was
  rendered, so the output never changed and the scores compounded.

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

# _detect_intent calls this one "code" ("function", "implements", "routes.py").
_CODE_QUESTION = "which function in routes.py implements the webhook handler"

_CODE_BOOSTS = {3.0, 0.5}
_DOC_BOOSTS = {2.0, 0.7}


def _fake_embed(texts: list[str]) -> list[list[float]]:
    out = []
    for t in texts:
        vec = np.zeros(_DIM, dtype=np.float32)
        for tok in t.lower().replace("\n", " ").split():
            vec[int.from_bytes(hashlib.md5(tok.encode()).digest()[:4], "little") % _DIM] += 1.0
        out.append(vec.tolist())
    return out


def _new_mind(root: Path, **kwargs):
    from neuralmind.core import NeuralMind

    mind = NeuralMind(str(root), backend_type="turbovec", enable_synapses=False, **kwargs)
    mind.embedder._embed_fn = _fake_embed
    mind.notice_stream = io.StringIO()
    return mind


@pytest.fixture(scope="module")
def project(tmp_path_factory) -> Path:
    root = tmp_path_factory.mktemp("retrieval") / "proj"
    shutil.copytree(_FIXTURE, root, ignore=shutil.ignore_patterns(".neuralmind"))
    mind = _new_mind(root)
    try:
        assert mind.build(regenerate_graph=True)["success"]
    finally:
        mind.close()
    return root


@pytest.fixture
def mind(project):
    m = _new_mind(project)
    yield m
    m.close()


# --------------------------------------------------------------------------- #
# query_type
# --------------------------------------------------------------------------- #
def test_query_type_sets_the_intent_l3_ranks_with(mind):
    auto = mind.query(_CODE_QUESTION, learn=False)
    code = mind.query(_CODE_QUESTION, query_type="code", learn=False)
    docs = mind.query(_CODE_QUESTION, query_type="docs", learn=False)

    assert auto.intent == "code"  # precondition: detected as a code question
    assert code.intent == "code"
    assert docs.intent == "docs"
    assert docs.intent_source == code.intent_source == "query_type"

    assert {h.get("_intent_boost") for h in code.top_search_hits} <= _CODE_BOOSTS
    assert {h.get("_intent_boost") for h in docs.top_search_hits} <= _DOC_BOOSTS


def test_query_type_changes_the_rendered_context(mind):
    code = mind.query(_CODE_QUESTION, query_type="code", learn=False)
    docs = mind.query(_CODE_QUESTION, query_type="docs", learn=False)
    assert code.context != docs.context


def test_query_type_matching_the_detected_intent_boosts_once(mind):
    auto = mind.query(_CODE_QUESTION, learn=False)
    code = mind.query(_CODE_QUESTION, query_type="code", learn=False)

    auto_scores = {h["id"]: h["score"] for h in auto.top_search_hits}
    code_scores = {h["id"]: h["score"] for h in code.top_search_hits}
    assert code_scores == pytest.approx(auto_scores)
    assert code.context == auto.context
