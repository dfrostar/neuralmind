"""onnx_embedder.py — ChromaDB-free MiniLM text embeddings
=========================================================

Owns embedding generation so the TurboVec backend (and, ahead, NeuralMind as a
whole) needs **zero ChromaDB**. Produces vectors byte-compatible with ChromaDB's
``DefaultEmbeddingFunction`` by reusing the *same* model (``all-MiniLM-L6-v2``
ONNX) and the *same* pipeline (tokenize → ONNX → attention-masked mean-pool →
L2-normalize), on just ``onnxruntime`` + ``tokenizers`` + ``numpy``.

Why: ChromaDB drags in a large transitive tree (FastAPI, kubernetes client,
OpenTelemetry, grpcio, …) and the recurring ``CVE-2026-45829`` advisory surface.
The vector *search* already moved to TurboVec (#204/#205); this moves the last
ChromaDB-only responsibility — embedding — off it too.

Model resolution order for the extracted ONNX folder (``model.onnx`` +
``tokenizer.json``):

1. ``$NEURALMIND_ONNX_MODEL_DIR`` (if it contains ``model.onnx``);
2. NeuralMind's own cache (``~/.cache/neuralmind/onnx_models/...``);
3. an existing ChromaDB cache (``~/.cache/chroma/onnx_models/...``) — so an
   installed-ChromaDB box reuses the already-downloaded model with no refetch;
4. download the same archive ChromaDB uses (SHA256-verified) into (2).
"""

from __future__ import annotations

import hashlib
import os
import tarfile
import time
import urllib.error
import urllib.request
from functools import cached_property
from pathlib import Path

import numpy as np

# The exact artifact ChromaDB's DefaultEmbeddingFunction uses, pinned by hash so
# a corrupted or swapped download fails loudly.
_MODEL_NAME = "all-MiniLM-L6-v2"
_ARCHIVE_URL = "https://chroma-onnx-models.s3.amazonaws.com/all-MiniLM-L6-v2/onnx.tar.gz"
_ARCHIVE_SHA256 = "913d7300ceae3b2dbc2c50d1de4baacab4be7b9380491c27fab7418616a16ec3"
_MAX_TOKENS = 256
_BATCH = 32
_DOWNLOAD_RETRIES = 3

_NM_CACHE = Path.home() / ".cache" / "neuralmind" / "onnx_models" / _MODEL_NAME / "onnx"
_CHROMA_CACHE = Path.home() / ".cache" / "chroma" / "onnx_models" / _MODEL_NAME / "onnx"


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


class OnnxMiniLMEmbedder:
    """ChromaDB-free ``all-MiniLM-L6-v2`` embedder (callable: texts → vectors)."""

    dim = 384

    def __init__(self, model_dir: str | os.PathLike[str] | None = None):
        """Create an ONNX MiniLM embedder.

        Args:
            model_dir: Optional explicit path to the model folder.
        """
        self._explicit_dir = Path(model_dir) if model_dir else None

    # ---------------------------------------------------------------- model dir
    def _resolve_model_dir(self) -> Path:
        """Locate the ONNX model folder (env → cache → chroma cache → download).

        Returns:
            Path to folder containing model.onnx + tokenizer.json.
        """
        env = os.environ.get("NEURALMIND_ONNX_MODEL_DIR")
        for cand in (
            self._explicit_dir,
            Path(env) if env else None,
            _NM_CACHE,
            _CHROMA_CACHE,
        ):
            if cand and (cand / "model.onnx").exists() and (cand / "tokenizer.json").exists():
                return cand
        # Nothing on disk — fetch the archive into NeuralMind's own cache.
        self._download_into(_NM_CACHE)
        return _NM_CACHE

    def _download_into(self, dest_onnx_dir: Path) -> None:
        """Download + verify + extract the ONNX archive into dest_onnx_dir.

        Args:
            dest_onnx_dir: Target folder for extracted model.onnx.

        Raises:
            ValueError: If SHA256 mismatch (corrupted/tampered).
        """
        # The archive extracts to an ``onnx/`` folder; download+extract one level up.
        root = dest_onnx_dir.parent
        root.mkdir(parents=True, exist_ok=True)
        archive = root / "onnx.tar.gz"
        for attempt in range(1, _DOWNLOAD_RETRIES + 1):
            try:
                urllib.request.urlretrieve(_ARCHIVE_URL, archive)  # noqa: S310 - pinned https URL
                break
            except (urllib.error.URLError, OSError):
                archive.unlink(missing_ok=True)
                if attempt >= _DOWNLOAD_RETRIES:
                    raise
                time.sleep(0.5 * attempt)
        actual = _sha256(archive)
        if actual != _ARCHIVE_SHA256:
            archive.unlink(missing_ok=True)
            raise ValueError(
                f"downloaded MiniLM archive SHA256 {actual} != expected "
                f"{_ARCHIVE_SHA256} (corrupted or tampered download)"
            )
        with tarfile.open(archive, "r:gz") as tar:
            tar.extractall(root)  # noqa: S202 - trusted, hash-verified archive
        archive.unlink(missing_ok=True)

    # ---------------------------------------------------------------- lazy load
    @cached_property
    def _tokenizer(self):
        from tokenizers import Tokenizer

        tok = Tokenizer.from_file(str(self._resolve_model_dir() / "tokenizer.json"))
        # sentence-transformers uses 256 even though the HF config says 128.
        tok.enable_truncation(max_length=_MAX_TOKENS)
        tok.enable_padding(pad_id=0, pad_token="[PAD]", length=_MAX_TOKENS)
        return tok

    @staticmethod
    def _session_options():
        """Build ORT session options, honoring ``NEURALMIND_ORT_THREADS``.

        By default onnxruntime sizes its intra-op thread pool to the host's
        core count, and the parallel reduction order changes the last bits of
        the embedding floats. Downstream, near-tie rankings (and TurboQuant
        quantization buckets) can flip on those bits — so the same commit can
        rank two near-equal candidates differently on runners that differ only
        in core count. ``NEURALMIND_ORT_THREADS=1`` pins the pool for a
        machine-independent summation order; the benchmark harness sets it so
        its published numbers are not a function of the runner it drew.
        Unset (the default) keeps ORT's own sizing — indexing throughput on
        real repos matters more than bit-stable floats there.
        """
        import onnxruntime as ort

        so = ort.SessionOptions()
        so.log_severity_level = 3
        so.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
        threads = os.environ.get("NEURALMIND_ORT_THREADS", "").strip()
        if threads:
            try:
                n = int(threads)
            except ValueError:
                n = 0  # invalid value → keep ORT defaults
            if n > 0:
                so.intra_op_num_threads = n
                so.inter_op_num_threads = 1
        return so

    @cached_property
    def _session(self):
        import onnxruntime as ort

        so = self._session_options()
        providers = ort.get_available_providers()
        # CoreML is slower than CPU for this tiny model; prefer CPU when present.
        providers = [p for p in providers if p != "CoreMLExecutionProvider"]
        return ort.InferenceSession(
            str(self._resolve_model_dir() / "model.onnx"), sess_options=so, providers=providers
        )

    # ------------------------------------------------------------------ encode
    @staticmethod
    def _normalize(v: np.ndarray) -> np.ndarray:
        norm = np.linalg.norm(v, axis=1)
        norm[norm == 0] = 1e-12
        return (v / norm[:, np.newaxis]).astype(np.float32)

    def embed(self, texts: list[str]) -> np.ndarray:
        """Return an ``(n, 384)`` float32 array of unit-normalised embeddings."""
        if not texts:
            return np.zeros((0, self.dim), dtype=np.float32)
        out: list[np.ndarray] = []
        for i in range(0, len(texts), _BATCH):
            batch = texts[i : i + _BATCH]
            encoded = [self._tokenizer.encode(d) for d in batch]
            input_ids = np.array([e.ids for e in encoded], dtype=np.int64)
            attention_mask = np.array([e.attention_mask for e in encoded], dtype=np.int64)
            onnx_input = {
                "input_ids": input_ids,
                "attention_mask": attention_mask,
                "token_type_ids": np.zeros_like(input_ids),
            }
            last_hidden = self._session.run(None, onnx_input)[0]
            # Attention-masked mean pooling (identical to ChromaDB / S-BERT).
            mask = np.broadcast_to(np.expand_dims(attention_mask, -1), last_hidden.shape)
            pooled = np.sum(last_hidden * mask, axis=1) / np.clip(
                mask.sum(axis=1), a_min=1e-9, a_max=None
            )
            out.append(self._normalize(pooled))
        return np.concatenate(out)

    def __call__(self, texts: list[str]) -> list[list[float]]:
        """Embed texts and return as a list of float lists.

        Args:
            texts: Input strings to embed.

        Returns:
            List of 384-dim unit-normalized vectors.
        """
        return self.embed(texts).tolist()
