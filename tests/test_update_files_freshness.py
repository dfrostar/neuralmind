"""An incremental ``update_files`` leaves the index as fresh as a build (H6).

``neuralmind watch --reindex`` re-indexes edited files through
``NeuralMind.update_files``. It pruned removed symbols from the vector store
but left the unified BM25 index, its ``index_generation`` stamp and the graph
fingerprint in ``build_status.json`` as the last build wrote them, so deleted
symbols kept coming back as keyword hits and every later load reported the
index out of step with its graph.

Embeddings use a deterministic hashing function injected into the turbovec
backend, so nothing here needs the ONNX model.
"""

from __future__ import annotations

import hashlib
import io
from pathlib import Path

import numpy as np
import pytest

from neuralmind import graphgen
from neuralmind.freshness import index_graph_mismatch

pytest.importorskip("turbovec")
pytestmark = pytest.mark.skipif(not graphgen.is_available(), reason="tree-sitter not installed")

_DIM = 32

_BILLING = '''"""Billing helpers."""


def charge_card(amount):
    """Charge a customer's card."""
    return amount


def refund_payment(payment_id):
    """Refund a payment."""
    return payment_id
'''

_DELETED = '''

def zebracorn_quantum_reconcile(x):
    """Reconcile zebracorn quantum ledgers."""
    return x
'''

_ADDED = '''

def wombat_ledger_flux(y):
    """Flux the wombat ledger."""
    return y
'''

_DELETED_ID = "pkg_billing_py__zebracorn_quantum_reconcile_fn"
_ADDED_ID = "pkg_billing_py__wombat_ledger_flux_fn"


def _fake_embed(texts: list[str]) -> list[list[float]]:
    out = []
    for t in texts:
        vec = np.zeros(_DIM, dtype=np.float32)
        for tok in t.lower().replace("\n", " ").split():
            vec[int.from_bytes(hashlib.md5(tok.encode()).digest()[:4], "little") % _DIM] += 1.0
        out.append(vec.tolist())
    return out


def _mind(root: Path):
    from neuralmind.core import NeuralMind

    mind = NeuralMind(str(root), backend_type="turbovec", enable_synapses=False)
    mind.embedder._embed_fn = _fake_embed
    mind.notice_stream = io.StringIO()
    return mind


def _hits(mind, query: str) -> tuple[set[str], str]:
    res = mind.query(query, learn=False)
    return {str(h.get("id")) for h in res.top_search_hits}, res.context


@pytest.fixture
def project(tmp_path) -> Path:
    root = tmp_path / "proj"
    (root / "pkg").mkdir(parents=True)
    (root / "pkg" / "__init__.py").write_text("", encoding="utf-8")
    (root / "pkg" / "billing.py").write_text(_BILLING + _DELETED, encoding="utf-8")
    (root / "pkg" / "users.py").write_text(
        '"""Users."""\n\n\ndef find_user(user_id):\n    """Look up a user."""\n'
        "    return user_id\n",
        encoding="utf-8",
    )
    return root


@pytest.fixture
def updated(project):
    """A built index, then the zebracorn function deleted via ``update_files``."""
    mind = _mind(project)
    assert mind.build(regenerate_graph=True)["success"]
    ids, _ = _hits(mind, "zebracorn_quantum_reconcile")
    assert _DELETED_ID in ids  # precondition: findable before the delete

    billing = project / "pkg" / "billing.py"
    billing.write_text(_BILLING, encoding="utf-8")
    stats = mind.update_files([str(billing)])
    assert stats["success"] and stats["pruned"] >= 1
    return project, mind


def test_deleted_symbol_gone_in_same_instance(updated):
    _, mind = updated
    ids, context = _hits(mind, "zebracorn_quantum_reconcile")
    assert not any("zebracorn" in i for i in ids)
    assert "zebracorn" not in context


def test_deleted_symbol_gone_in_fresh_instance(updated):
    project, _ = updated
    fresh = _mind(project)
    ids, context = _hits(fresh, "zebracorn_quantum_reconcile")
    assert not any("zebracorn" in i for i in ids)
    assert "zebracorn" not in context
    assert "out of step" not in fresh.notice_stream.getvalue()


def test_no_index_graph_mismatch_after_update(updated):
    project, _ = updated
    assert index_graph_mismatch(project) == ""


def test_added_symbol_found_by_keyword_in_fresh_instance(updated):
    project, mind = updated
    billing = project / "pkg" / "billing.py"
    billing.write_text(_BILLING + _ADDED, encoding="utf-8")
    assert mind.update_files([str(billing)])["success"]

    fresh = _mind(project)
    assert fresh.ensure_ready().get("loaded")  # loads the index as it stands, no build
    keyword_ids = {
        str(h.get("id")) for h in fresh.selector._unified_bm25_search("wombat_ledger_flux", 10)
    }
    assert _ADDED_ID in keyword_ids
    assert index_graph_mismatch(project) == ""


def test_full_build_after_update_sees_nothing_stale(updated):
    project, _ = updated
    result = _mind(project).build()
    assert result["success"]
    assert result.get("nodes_removed", 0) == 0  # update_files already pruned
    assert index_graph_mismatch(project) == ""
    ids, _ = _hits(_mind(project), "zebracorn_quantum_reconcile")
    assert not any("zebracorn" in i for i in ids)
