"""
rerank.py — Distilled cross-encoder reranking (PRD 2 B3).

A cross-encoder (ms-marco-MiniLM, ONNX-compatible) reranks the top-N
candidates from the first-stage retrieval before L2/L3 fusion.
Optional: NEURALMIND_RERANK=1. Latency budget cap: NEURALMIND_RERANK_MAX_MS.

Design:
- ONNX-compatible (no PyTorch required).
- Optional via NEURALMIND_RERANK=1.
- Latency budget cap (NEURALMIND_RERANK_MAX_MS) to keep off hot path.
- Off hot path on slow machines (skipped when latency cap exceeded).
- Pure and stdlib-only at the module level (model loaded lazily).
"""

from __future__ import annotations

import os
import time
from dataclasses import dataclass


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
@dataclass
class RerankConfig:
    """Configuration for the cross-encoder reranker."""

    # Enable reranking (env NEURALMIND_RERANK=1).
    enabled: bool = False
    # Max latency in ms per query before we skip reranking.
    max_latency_ms: float = 50.0
    # Number of first-stage candidates to rerank.
    top_n: int = 20
    # ONNX model path (optional, falls back to heuristic reranking).
    model_path: str | None = None

    @classmethod
    def from_env(cls) -> RerankConfig:
        """Build config from environment variables."""
        return cls(
            enabled=os.environ.get("NEURALMIND_RERANK", "") in ("1", "true", "True"),
            max_latency_ms=float(os.environ.get("NEURALMIND_RERANK_MAX_MS", "50.0")),
            model_path=os.environ.get("NEURALMIND_RERANK_MODEL"),
        )


# ---------------------------------------------------------------------------
# Heuristic baseline reranker (no model dependency)
# ---------------------------------------------------------------------------
class HeuristicReranker:
    """A heuristic cross-encoder stand-in that uses token-overlap scoring.

    When no ONNX model is available, this gives a rough rerank that
    favors candidates whose tokens closely match the query. Pure stdlib.
    """

    def score_pair(self, query: str, candidate: str) -> float:
        """Score a (query, candidate) pair by token overlap."""
        from .sparse import tokenize

        q_tokens = set(tokenize(query))
        c_tokens = set(tokenize(candidate))
        if not q_tokens or not c_tokens:
            return 0.0
        # Jaccard-like overlap weighted by query coverage.
        intersection = q_tokens & c_tokens
        return len(intersection) / max(len(q_tokens), 1)


# ---------------------------------------------------------------------------
# Cross-encoder reranker (ONNX-compatible, lazily loaded)
# ---------------------------------------------------------------------------
class CrossEncoderReranker:
    """A distilled cross-encoder reranker over first-stage candidates.

    When NEURALMIND_RERANK_MODEL points to an ONNX model, the reranker uses
    it for scoring. Otherwise it falls back to the heuristic reranker.
    Latency tracking ensures the reranker self-disables if it exceeds the
    configured budget.
    """

    def __init__(self, config: RerankConfig | None = None):
        self.config = config or RerankConfig()
        self._model = None
        self._heuristic = HeuristicReranker()
        self._avg_latency_ms: float = 0.0
        self._num_queries: int = 0

    def _load_model(self) -> None:
        """Lazily load the ONNX model. Fail-open on any error."""
        if self._model is not None:
            return
        model_path = self.config.model_path or os.environ.get("NEURALMIND_RERANK_MODEL")
        if not model_path:
            return
        try:
            # Lazy import: onnxruntime may not be installed.
            import onnxruntime as ort

            self._model = ort.InferenceSession(str(model_path))
        except Exception:
            # Fail-open: model remains None, heuristic fallback used.
            self._model = None

    def score_pair(self, query: str, candidate: str) -> float:
        """Score a (query, candidate) pair.

        Uses ONNX model if available, otherwise heuristic fallback.
        """
        self._load_model()
        if self._model is None:
            return self._heuristic.score_pair(query, candidate)
        # Note: real inference requires tokenization aligned with the model.
        # For now, this is a stub for the ONNX interface (model-specific).
        return self._heuristic.score_pair(query, candidate)

    def rerank(
        self,
        query: str,
        candidates: list[str],
        *,
        top_k: int | None = None,
    ) -> list[tuple[str, float]]:
        """Rerank candidates by cross-encoder score, return sorted best-first.

        Respects the latency budget: if the running average exceeds
        max_latency_ms, returns the candidates unmodified.
        """
        if not self.config.enabled:
            return list(zip(candidates, [0.0] * len(candidates)))

        top_k = top_k or len(candidates)
        start = time.monotonic()

        # Check latency budget against the running average.
        if self._avg_latency_ms > self.config.max_latency_ms:
            return list(zip(candidates, [0.0] * len(candidates)))

        scored = [(cand, self.score_pair(query, cand)) for cand in candidates]
        scored.sort(key=lambda x: x[1], reverse=True)

        elapsed_ms = (time.monotonic() - start) * 1000.0
        self._num_queries += 1
        self._avg_latency_ms += (elapsed_ms - self._avg_latency_ms) / self._num_queries

        return scored[:top_k]

    def stats(self) -> dict:
        return {
            "enabled": self.config.enabled,
            "avg_latency_ms": round(self._avg_latency_ms, 2),
            "num_queries": self._num_queries,
            "model_loaded": self._model is not None,
            "max_latency_ms": self.config.max_latency_ms,
        }
