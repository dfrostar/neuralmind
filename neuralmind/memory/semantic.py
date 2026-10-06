"""semantic.py — meaning-based ranking for decision search.

Keyword search (``store.py``) finds a decision only when the question shares a
word with it: "where do we verify who is calling an endpoint?" never reaches
"Use per-handler authentication middleware". This module ranks decisions by
meaning instead. Each decision's title and rationale — the fields keyword
search covers — are embedded with the same local ``all-MiniLM-L6-v2`` model
the code index uses (``neuralmind.onnx_embedder``), and a question is compared
with them by cosine similarity.

Search modes (``DecisionStore.search(..., mode=...)``):

- ``keyword`` — FTS5 word matching, LIKE without FTS5 (``store.py``)
- ``semantic`` — cosine similarity only; decisions below ``MIN_SIMILARITY``
  are not matches
- ``hybrid`` — both rankings fused by reciprocal rank fusion

Local and offline: vectors are computed on this machine, cached in the
``decision_vectors`` table of ``memory.db``, and recomputed when a decision's
title or rationale, or the model, changes. Search never downloads the model.
When it isn't on disk (``neuralmind build`` fetches it once), ``hybrid``
falls back to keyword results and says so, and ``semantic`` raises
``SemanticSearchUnavailableError``.

Stdlib-only at import, like the rest of the decision store; numpy and the
ONNX runtime load on first use.
"""

from __future__ import annotations

import hashlib
import importlib.util
import logging
import os
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)

SEARCH_MODES: tuple[str, ...] = ("keyword", "semantic", "hybrid")

# The mode used when a caller names none and $NEURALMIND_DECISION_SEARCH is
# unset.
DEFAULT_MODE = "hybrid"

MODE_ENV = "NEURALMIND_DECISION_SEARCH"

# Cosine similarity below which a decision is not a semantic match, so a
# question nothing answers doesn't get the nearest decisions regardless.
# Committed before semantic search was run on the eval set
# (tests/memory/fixtures/decision_queries.json, _paraphrase_preregistration)
# and not tuned on it.
MIN_SIMILARITY = 0.30

# Reciprocal rank fusion constant: the usual value, not tuned here.
RRF_K = 60

# Texts per ONNX session. Each chunk runs in a fresh session because
# onnxruntime 1.29 on Python 3.14 deadlocks after 2-3 runs on a reused one
# (see onnx_embedder.py).
EMBED_CHUNK = 32

DEFAULT_MODEL_ID = "all-MiniLM-L6-v2"


class SemanticSearchUnavailableError(RuntimeError):
    """Semantic ranking can't run here: a runtime or the model is missing, or embedding failed."""


def resolve_mode(mode: str | None) -> str:
    """The search mode to use: ``mode``, else ``$NEURALMIND_DECISION_SEARCH``, else ``DEFAULT_MODE``.

    Case-insensitive. An unknown ``mode`` raises ``ValueError``. An unknown
    environment value is logged and ignored, so a typo in a shell profile
    can't break every search.
    """
    if mode is not None and str(mode).strip():
        value = str(mode).strip().lower()
        if value not in SEARCH_MODES:
            raise ValueError(
                f"unknown search mode {mode!r}; expected one of {', '.join(SEARCH_MODES)}"
            )
        return value
    env = os.environ.get(MODE_ENV, "").strip().lower()
    if env:
        if env in SEARCH_MODES:
            return env
        logger.warning(
            "[memory] ignoring %s=%r; expected one of %s", MODE_ENV, env, ", ".join(SEARCH_MODES)
        )
    return DEFAULT_MODE


def decision_text(title: str, rationale: str) -> str:
    """The text embedded for a decision: the same fields keyword search covers."""
    return f"{title}\n{rationale}"


def content_sha(text: str) -> str:
    """Fingerprint of embedded text; a cached vector is reused only while it matches."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class DecisionEmbedder:
    """An embedding function and the id of the model behind it.

    ``embed`` maps a list of texts to an ``(n, dim)`` array-like of vectors.
    ``model_id`` is stored with every cached vector, so switching models
    re-embeds instead of comparing vectors from two models.
    """

    model_id: str
    embed: Callable[[list[str]], Any]


def load_default_embedder() -> DecisionEmbedder:
    """The local MiniLM embedder, provided it can run without the network.

    Raises:
        SemanticSearchUnavailableError: numpy, onnxruntime or tokenizers isn't
            installed, or the model isn't on disk.
    """
    missing = [
        name
        for name in ("numpy", "onnxruntime", "tokenizers")
        if importlib.util.find_spec(name) is None
    ]
    if missing:
        raise SemanticSearchUnavailableError(f"{', '.join(missing)} not installed")

    from neuralmind.onnx_embedder import OnnxMiniLMEmbedder

    model = OnnxMiniLMEmbedder()
    if model.local_model_dir() is None:
        raise SemanticSearchUnavailableError(
            "the embedding model isn't on disk; `neuralmind build` downloads it once"
        )

    def embed(texts: list[str]) -> Any:
        import numpy as np

        # embed() opens a fresh session per call, so one chunk = one session.
        chunks = [
            model.embed(texts[i : i + EMBED_CHUNK]) for i in range(0, len(texts), EMBED_CHUNK)
        ]
        return np.concatenate(chunks) if chunks else np.zeros((0, model.dim), dtype=np.float32)

    return DecisionEmbedder(model_id=DEFAULT_MODEL_ID, embed=embed)


def embed_texts(embedder: DecisionEmbedder, texts: list[str]) -> Any:
    """Embed ``texts`` as an ``(n, dim)`` float32 array of unit vectors."""
    import numpy as np

    matrix = np.asarray(embedder.embed(texts), dtype=np.float32)
    if matrix.ndim != 2 or matrix.shape[0] != len(texts):
        raise ValueError(
            f"embedder returned shape {matrix.shape} for {len(texts)} texts; expected (n, dim)"
        )
    norms = np.linalg.norm(matrix, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    return matrix / norms


def rank_by_similarity(
    query: Any, candidates: Sequence[tuple[str, Any]], floor: float = MIN_SIMILARITY
) -> list[tuple[str, float]]:
    """``(id, cosine)`` for each candidate at or above ``floor``, most similar first.

    ``query`` and the candidate vectors are unit vectors, so the dot product
    is the cosine. Equal similarities keep the candidates' order.
    """
    import numpy as np

    scored = [(cid, float(np.dot(query, vector))) for cid, vector in candidates]
    kept = [(cid, sim) for cid, sim in scored if sim >= floor]
    return sorted(kept, key=lambda item: -item[1])


def rrf(rankings: Sequence[Sequence[str]], k: int = RRF_K) -> list[str]:
    """Fuse ranked id lists by reciprocal rank fusion.

    Each list adds ``1 / (k + rank)`` to every id it ranks. Equal scores go
    to the id with the better single rank, then to the earlier list (keyword
    before semantic in hybrid search), so the order is deterministic.
    """
    score: dict[str, float] = {}
    best: dict[str, tuple[int, int]] = {}
    for list_index, ranking in enumerate(rankings):
        for rank, item in enumerate(ranking, 1):
            score[item] = score.get(item, 0.0) + 1.0 / (k + rank)
            if item not in best or (rank, list_index) < best[item]:
                best[item] = (rank, list_index)
    return sorted(score, key=lambda item: (-score[item], best[item]))
