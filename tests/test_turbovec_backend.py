"""Mechanics tests for the TurboVec EmbeddingBackend POC (issue #204).

Skips cleanly where ``turbovec``/``numpy`` aren't installed (it's an optional,
opt-in backend). Uses a deterministic bag-of-words ``embed_fn`` so the test
needs neither chromadb nor the MiniLM ONNX model — it exercises the backend's
own logic (id mapping, search ranking, allowlist filtering, persistence,
deletion), not embedding quality.

    python -m pytest tests/test_turbovec_backend.py
"""

from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

if importlib.util.find_spec("turbovec") is None or importlib.util.find_spec("numpy") is None:
    raise unittest.SkipTest("turbovec/numpy not installed (optional backend)")

import numpy as np  # noqa: E402

from neuralmind.turbovec_backend import TurboVecEmbedder  # noqa: E402

_DIM = 32
_VOCAB_TOKENS = ("auth", "login", "billing", "invoice", "user", "db", "token", "refund")


def _fake_embed(texts: list[str]) -> list[list[float]]:
    """Deterministic bag-of-words hashing embedder (no model needed)."""
    out = []
    for t in texts:
        vec = np.zeros(_DIM, dtype=np.float32)
        for tok in t.lower().replace("\n", " ").split():
            vec[hash(tok) % _DIM] += 1.0
        out.append(vec.tolist())
    return out


def _write_graph(root: Path, nodes: list[dict]) -> None:
    out = root / "graphify-out"
    out.mkdir(parents=True, exist_ok=True)
    (out / "graph.json").write_text(json.dumps({"nodes": nodes, "edges": []}), encoding="utf-8")


def _nodes() -> list[dict]:
    return [
        {"id": "n_auth", "label": "authenticate_user", "file_type": "function",
         "source_file": "auth/handlers.py", "community": 0},
        {"id": "n_login", "label": "login_route", "file_type": "function",
         "source_file": "auth/routes.py", "community": 0},
        {"id": "n_billing", "label": "charge_card", "file_type": "function",
         "source_file": "billing/stripe.py", "community": 1},
        {"id": "n_invoice", "label": "send_invoice", "file_type": "function",
         "source_file": "billing/invoice.py", "community": 1},
        {"id": "n_user", "label": "user_model", "file_type": "model",
         "source_file": "users/models.py", "community": 2},
    ]


class TurboVecBackendTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        _write_graph(self.root, _nodes())
        self.db = str(self.root / "tv")

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def _backend(self) -> TurboVecEmbedder:
        return TurboVecEmbedder(str(self.root), db_path=self.db, embed_fn=_fake_embed)

    def test_embed_counts_and_idempotent_skip(self) -> None:
        be = self._backend()
        stats = be.embed_nodes()
        self.assertEqual(stats["added"], 5)
        self.assertEqual(stats["updated"], 0)
        # Re-embedding the same graph skips everything (content hashes match).
        again = be.embed_nodes()
        self.assertEqual(again["skipped"], 5)
        self.assertEqual(again["added"], 0)
        be.close()

    def test_search_ranks_relevant_node_first(self) -> None:
        be = self._backend()
        be.embed_nodes()
        results = be.search("authenticate_user", n=3)
        self.assertTrue(results)
        self.assertEqual(results[0]["id"], "n_auth")
        # result shape matches the GraphEmbedder contract
        self.assertIn("document", results[0])
        self.assertIn("metadata", results[0])
        self.assertIn("score", results[0])
        be.close()

    def test_allowlist_filter_by_community(self) -> None:
        be = self._backend()
        be.embed_nodes()
        # Restrict to community 1 (billing) — auth nodes must not appear.
        results = be.search("charge_card invoice", n=5, community=1)
        self.assertTrue(results)
        self.assertTrue(all(r["metadata"]["community"] == 1 for r in results))
        be.close()

    def test_get_nodes_by_ids_roundtrip(self) -> None:
        be = self._backend()
        be.embed_nodes()
        got = be.get_nodes_by_ids(["n_billing", "missing", "n_user"])
        ids = {g["id"] for g in got}
        self.assertEqual(ids, {"n_billing", "n_user"})
        be.close()

    def test_persistence_reload(self) -> None:
        be = self._backend()
        be.embed_nodes()
        be.close()
        # Re-open from disk: index + store survive, search still works.
        reopened = self._backend()
        self.assertEqual(reopened.get_stats()["total_nodes"], 5)
        results = reopened.search("send_invoice", n=1)
        self.assertEqual(results[0]["id"], "n_invoice")
        reopened.close()

    def test_delete_nodes(self) -> None:
        be = self._backend()
        be.embed_nodes()
        removed = be.delete_nodes(["n_user"])
        self.assertEqual(removed, 1)
        self.assertEqual(be.get_stats()["total_nodes"], 4)
        self.assertEqual(be.get_nodes_by_ids(["n_user"]), [])
        be.close()

    def test_stats_shape(self) -> None:
        be = self._backend()
        be.embed_nodes()
        stats = be.get_stats()
        self.assertEqual(stats["total_nodes"], 5)
        self.assertEqual(stats["backend"], "turbovec")
        self.assertGreaterEqual(stats["communities"], 1)
        be.close()


if __name__ == "__main__":
    unittest.main(verbosity=2)
