"""Tests for the ChromaDB-free ONNX MiniLM embedder (issue #204).

Skips cleanly when the runtime deps (onnxruntime/tokenizers/numpy) are missing,
or when the model isn't already on disk — so CI never triggers the ~90 MB
download. Run locally (or after one ChromaDB/embed call has cached the model) to
exercise the real pipeline.

    python -m pytest tests/test_onnx_embedder.py
"""

from __future__ import annotations

import importlib.util
import os
import sys
import unittest
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))


def _missing(*mods: str) -> bool:
    return any(importlib.util.find_spec(m) is None for m in mods)


if _missing("numpy", "onnxruntime", "tokenizers"):
    _skip = "onnxruntime/tokenizers/numpy not installed"
    try:
        import pytest

        pytest.skip(_skip, allow_module_level=True)
    except ImportError:  # pragma: no cover
        raise unittest.SkipTest(_skip) from None

import numpy as np  # noqa: E402

from neuralmind.onnx_embedder import _CHROMA_CACHE, _NM_CACHE, OnnxMiniLMEmbedder  # noqa: E402


def _model_on_disk() -> Path | None:
    env = os.environ.get("NEURALMIND_ONNX_MODEL_DIR")
    for cand in (Path(env) if env else None, _NM_CACHE, _CHROMA_CACHE):
        if cand and (cand / "model.onnx").exists() and (cand / "tokenizer.json").exists():
            return cand
    return None


if _model_on_disk() is None:
    _skip = "MiniLM model not cached on disk; skipping to avoid a network download"
    try:
        import pytest

        pytest.skip(_skip, allow_module_level=True)
    except ImportError:  # pragma: no cover
        raise unittest.SkipTest(_skip) from None


class OnnxEmbedderTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.embedder = OnnxMiniLMEmbedder()

    def test_shape_and_dim(self) -> None:
        vecs = self.embedder.embed(["hello world", "authenticate_user"])
        self.assertEqual(vecs.shape, (2, 384))
        self.assertEqual(self.embedder.dim, 384)

    def test_unit_normalized(self) -> None:
        vecs = self.embedder.embed(["a billing invoice", "jwt token refresh"])
        norms = np.linalg.norm(vecs, axis=1)
        self.assertTrue(np.allclose(norms, 1.0, atol=1e-5), f"norms={norms}")

    def test_deterministic(self) -> None:
        a = self.embedder.embed(["same input text"])
        b = self.embedder.embed(["same input text"])
        self.assertTrue(np.array_equal(a, b))

    def test_empty_input(self) -> None:
        vecs = self.embedder.embed([])
        self.assertEqual(vecs.shape, (0, 384))

    def test_call_returns_lists(self) -> None:
        out = self.embedder(["x", "y"])
        self.assertIsInstance(out, list)
        self.assertEqual(len(out), 2)
        self.assertEqual(len(out[0]), 384)
        self.assertIsInstance(out[0][0], float)

    def test_semantic_similarity_ordering(self) -> None:
        # Related sentences should be closer than unrelated ones.
        v = self.embedder.embed(
            ["user authentication and login", "login and auth for users", "stripe billing refund"]
        )
        sim_related = float(np.dot(v[0], v[1]))
        sim_unrelated = float(np.dot(v[0], v[2]))
        self.assertGreater(sim_related, sim_unrelated)


if __name__ == "__main__":
    unittest.main(verbosity=2)
