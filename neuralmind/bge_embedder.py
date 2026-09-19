"""
bge_embedder.py — ChromaDB-free BGE-large text embeddings
=========================================================

Optional larger embedding model for NeuralMind. Uses `BAAI/bge-large-en-v1.5`
(1024d) via `sentence-transformers` for significantly better recall on
domain-specific terms compared to the default `all-MiniLM-L6-v2` (384d).

This is an *opt-in* embedder — the default remains `all-MiniLM-L6-v2` for
backward compatibility. Users select it via::

    neuralmind build . --embedder bge-large

(Note: the ``NEURALMIND_EMBEDDER`` env var is not currently read anywhere;
selection is via the CLI flag only.)

Model resolution order for the downloaded model folder:

1. ``$NEURALMIND_BGE_MODEL_DIR`` (if it contains ``pytorch_model.bin`` or ``model.safetensors``);
2. ``~/.cache/neuralmind/bge-large-en-v1.5/``;
3. Download via ``sentence-transformers`` (handles caching automatically).
"""

from __future__ import annotations

import os
from collections.abc import Callable
from pathlib import Path

import numpy as np

_MODEL_NAME = "BAAI/bge-large-en-v1.5"
_DIM = 1024
_MAX_TOKENS = 512
_BATCH = 16  # bge-large is ~2x slower per embedding; smaller batch to bound RSS

_NM_CACHE = Path.home() / ".cache" / "neuralmind" / _MODEL_NAME


class OnnxNotAvailableError(Exception):
    """Raised when sentence-transformers is not installed but bge-large was requested."""


class BGELargeEmbedder:
    """ChromaDB-free ``bge-large-en-v1.5`` embedder (callable: texts → vectors).

    Produces 1024d vectors — ~3× the dimensionality of the default
    ``all-MiniLM-L6-v2`` (384d). Significantly better recall on domain-specific
    terms at the cost of ~2× slower embedding speed and ~3× larger index size.
    """

    dim = _DIM

    def __init__(self, model_dir: str | os.PathLike[str] | None = None):
        self._explicit_dir = Path(model_dir) if model_dir else None
        self._model = None

    # ---------------------------------------------------------------- model
    def _resolve_model_dir(self) -> Path:
        """Locate the model folder (env → cache → download)."""
        env = os.environ.get("NEURALMIND_BGE_MODEL_DIR")
        for cand in (
            self._explicit_dir,
            Path(env) if env else None,
            _NM_CACHE,
        ):
            if cand and self._model_exists(cand):
                return cand
        # sentence-transformers will download into its own cache; we don't
        # need to pre-validate here since _load_model() handles that.
        return _NM_CACHE

    @staticmethod
    def _model_exists(path: Path) -> bool:
        """Check if a model folder contains the required files."""
        if not path.is_dir():
            return False
        # Accept either PyTorch or Safetensors format
        has_weights = (path / "pytorch_model.bin").exists() or (path / "model.safetensors").exists()
        has_config = (path / "config.json").exists()
        return has_weights and has_config

    def _load_model(self):
        """Lazy-load the sentence-transformers model."""
        if self._model is not None:
            return self._model
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError as exc:
            raise OnnxNotAvailableError(
                "The 'bge-large' embedder requires sentence-transformers. "
                "Install it with: pip install sentence-transformers"
            ) from exc

        model_dir = self._resolve_model_dir()
        if self._model_exists(model_dir):
            self._model = SentenceTransformer(str(model_dir))
        else:
            # sentence-transformers handles download + caching
            self._model = SentenceTransformer(_MODEL_NAME)
        return self._model

    # --------------------------------------------------------- embedding
    def embed(self, texts: list[str]) -> np.ndarray:
        """Embed ``texts`` into an ``(n, dim)`` array.

        BGE-large benefits from the ``query:`` prefix for retrieval tasks,
        but since NeuralMind embeds both queries and documents uniformly,
        we apply the prefix only at query time (handled by the caller).
        """
        model = self._load_model()
        vectors = model.encode(
            texts,
            show_progress_bar=False,
            normalize_embeddings=True,  # L2-normalize for cosine similarity
            batch_size=_BATCH,
        )
        return np.asarray(vectors, dtype=np.float32)

    def __call__(self, texts: list[str]) -> list[list[float]]:
        """ChromaDB-compatible interface (returns list[list[float]])."""
        return self.embed(texts).tolist()


# ----------------------------------------------------------------- registry
def get_embedder(name: str = "all-MiniLM-L6-v2") -> Callable[[list[str]], list[list[float]]]:
    """Get an embedder by name.

    Supported names:
    - ``all-MiniLM-L6-v2`` (default, 384d, fast, generic)
    - ``bge-large`` or ``bge-large-en-v1.5`` (1024d, slower, better domain recall)
    """
    if name in ("bge-large", "bge-large-en-v1.5"):
        return BGELargeEmbedder()
    if name in ("all-MiniLM-L6-v2", "minilm", "default"):
        from .onnx_embedder import OnnxMiniLMEmbedder

        return OnnxMiniLMEmbedder()
    raise ValueError(f"Unknown embedder: '{name}'. Available: all-MiniLM-L6-v2, bge-large")


def embedder_dim(name: str = "all-MiniLM-L6-v2") -> int:
    """Return the dimensionality of the given embedder."""
    if name in ("bge-large", "bge-large-en-v1.5"):
        return _DIM
    if name in ("all-MiniLM-L6-v2", "minilm", "default"):
        return 384
    raise ValueError(f"Unknown embedder: '{name}'")
