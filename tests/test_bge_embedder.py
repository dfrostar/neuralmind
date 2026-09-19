import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch


class TestEmbedderRegistry(unittest.TestCase):
    """Tests for the embedder registry and dimension lookup."""

    def test_default_embedder_dim(self):
        """Default embedder (all-MiniLM-L6-v2) produces 384d vectors."""
        from neuralmind.bge_embedder import embedder_dim

        self.assertEqual(embedder_dim("all-MiniLM-L6-v2"), 384)

    def test_bge_large_embedder_dim(self):
        """bge-large embedder produces 1024d vectors."""
        from neuralmind.bge_embedder import embedder_dim

        self.assertEqual(embedder_dim("bge-large"), 1024)
        self.assertEqual(embedder_dim("bge-large-en-v1.5"), 1024)

    def test_unknown_embedder_raises(self):
        """Unknown embedder name raises ValueError."""
        from neuralmind.bge_embedder import embedder_dim, get_embedder

        with self.assertRaises(ValueError):
            embedder_dim("unknown-model")
        with self.assertRaises(ValueError):
            get_embedder("unknown-model")

    def test_get_embedder_default(self):
        """Default embedder is OnnxMiniLMEmbedder."""
        from neuralmind.bge_embedder import get_embedder
        from neuralmind.onnx_embedder import OnnxMiniLMEmbedder

        embedder = get_embedder("all-MiniLM-L6-v2")
        self.assertIsInstance(embedder, OnnxMiniLMEmbedder)

    def test_get_embedder_bge_large(self):
        """bge-large returns BGELargeEmbedder."""
        from neuralmind.bge_embedder import BGELargeEmbedder, get_embedder

        embedder = get_embedder("bge-large")
        self.assertIsInstance(embedder, BGELargeEmbedder)
        self.assertEqual(embedder.dim, 1024)


class TestBGELargeEmbedder(unittest.TestCase):
    """Tests for the BGELargeEmbedder class."""

    def test_dim_attribute(self):
        """BGELargeEmbedder.dim is 1024."""
        from neuralmind.bge_embedder import BGELargeEmbedder

        embedder = BGELargeEmbedder()
        self.assertEqual(embedder.dim, 1024)

    def test_model_exists_false_for_empty_dir(self):
        """_model_exists returns False for empty directory."""
        from neuralmind.bge_embedder import BGELargeEmbedder

        embedder = BGELargeEmbedder()
        self.assertFalse(embedder._model_exists(Path("/nonexistent/path")))


class TestTurboVecEmbedderDim(unittest.TestCase):
    """Tests for TurboVecEmbedder.dim property with injected embedder."""

    def test_dim_from_injected_embedder(self):
        """TurboVecEmbedder.dim reflects injected embedder's dim."""
        from neuralmind.turbovec_backend import TurboVecEmbedder

        # Create a mock embedder with a dim attribute
        mock_embedder = MagicMock()
        mock_embedder.dim = 1024

        # Patch the imports and config
        with patch("neuralmind.turbovec_backend._default_embed_fn"):
            with patch.dict(sys.modules, {"turbovec": MagicMock()}):
                embedder = TurboVecEmbedder.__new__(TurboVecEmbedder)
                embedder._project_path = Path("/tmp")
                embedder._embed_fn = mock_embedder
                self.assertEqual(embedder.dim, 1024)

    def test_dim_fallback_to_default_when_no_embedder(self):
        """TurboVecEmbedder.dim resolves the default embedder's dim when none injected."""
        from neuralmind.turbovec_backend import TurboVecEmbedder

        with patch("neuralmind.turbovec_backend._default_embed_fn") as mock_default:
            mock_default.return_value.dim = 384
            with patch.dict(sys.modules, {"turbovec": MagicMock()}):
                embedder = TurboVecEmbedder.__new__(TurboVecEmbedder)
                embedder._project_path = Path("/tmp")
                embedder._embed_fn = None
                # No embedder injected, no stored dim → dim comes from the default embed_fn
                embedder._conn = MagicMock()  # Mock the SQLite connection
                embedder._conn.execute.return_value.fetchone.return_value = None  # No stored dim
                self.assertEqual(embedder.dim, 384)


class TestEmbedderMismatchDetection(unittest.TestCase):
    """Tests for the embedder mismatch detection in cli.py."""

    def test_check_embedder_mismatch_no_mismatch(self):
        """No warning when embedder matches stored dim."""
        import json

        from neuralmind.cli import _check_embedder_mismatch

        with tempfile.TemporaryDirectory() as tmpdir:
            meta_path = Path(tmpdir) / ".neuralmind" / "ir_meta.json"
            meta_path.parent.mkdir(parents=True, exist_ok=True)
            meta_path.write_text(json.dumps({"dim": 1024}))
            result = _check_embedder_mismatch(tmpdir, "bge-large")
            self.assertIsNone(result)

    def test_check_embedder_mismatch_with_mismatch(self):
        """Warning when embedder dim differs from stored dim."""
        import json

        from neuralmind.cli import _check_embedder_mismatch

        with tempfile.TemporaryDirectory() as tmpdir:
            meta_path = Path(tmpdir) / ".neuralmind" / "ir_meta.json"
            meta_path.parent.mkdir(parents=True, exist_ok=True)
            meta_path.write_text(json.dumps({"dim": 384}))
            result = _check_embedder_mismatch(tmpdir, "bge-large")
            self.assertIsNotNone(result)
            self.assertIn("dim=384", result)
            self.assertIn("1024", result)

    def test_check_embedder_mismatch_no_request(self):
        """No warning when no embedder requested."""
        from neuralmind.cli import _check_embedder_mismatch

        result = _check_embedder_mismatch("/tmp", None)
        self.assertIsNone(result)

    def test_check_embedder_mismatch_default_embedder(self):
        """No warning when default embedder requested."""
        from neuralmind.cli import _check_embedder_mismatch

        result = _check_embedder_mismatch("/tmp", "all-MiniLM-L6-v2")
        self.assertIsNone(result)


if __name__ == "__main__":
    unittest.main()
