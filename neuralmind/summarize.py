"""summarize.py — RAPTOR-style hierarchical summarization for L0-L3 (B4).

Replaces hand-tuned ``L0_MAX_TOKENS`` / ``L1_MAX_TOKENS`` constants with
a learned depth selector. RAPTOR-style recursive summarization at each
layer, operating within the IR contract (B1). Gated behind
``NEURALMIND_SUMMARIZE=1``; falls back to hand-tuned constants when
disabled or when the embed_fn is unavailable. Layer budgets remain
byte-compatible with the existing context selector.

Pure, stdlib-only, fail-open.

See Also:
    - ``neuralmind/context_selector.py`` — consumes SummaryResult
    - ``neuralmind/tuning.py`` — depth selector param definitions
    - ``tests/test_summarize.py`` — test cases

Version:
    0.53.0
"""

from __future__ import annotations

import logging
import os
import re
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from .tuning import effective_int

log = logging.getLogger(__name__)

# Depth selector defaults: how many hierarchical levels per layer.
DEFAULT_DEPTH = 3
MAX_DEPTH = 5


@dataclass
class SummaryResult:
    """A hierarchical summary with per-layer breakdown."""

    text: str
    depth_used: int
    source_length: int
    layer: int

    @property
    def tokens(self) -> int:
        return len(self.text) // 4  # chars-per-token fallback


class RaptorSummarizer:
    """Recursive RAPTOR-style summarization for a single layer.

    Uses extractive chunking + light-weight scoring when no embed_fn is
    available; switches to semantic clustering when an embed_fn is injected.
    """

    def __init__(
        self,
        depth: int | None = None,
        max_tokens_per_layer: int = 500,
        embed_fn: Callable[[str], list[float]] | None = None,
    ):
        self.depth = depth or DEFAULT_DEPTH
        self.max_tokens_per_layer = max_tokens_per_layer
        self.embed_fn = embed_fn

    def summarize(self, text: str, layer: int = 0) -> SummaryResult:
        """Recursive RAPTOR-style summarization.

        Splits ``text`` into chunks, scores each, then recursively
        summarizes the top-ranked chunks until budget is met.
        """
        if not text.strip():
            return SummaryResult("", 0, 0, layer)

        budget = self._budget_for_layer(layer)
        if len(text) // 4 <= budget:
            return SummaryResult(text, 1, len(text), layer)

        chunks = self._chunk(text, max_chars=max(budget * 4, 200))
        if len(chunks) <= 1:
            return SummaryResult(chunks[0] if chunks else "", 1, len(text), layer)

        # Score chunks: position + length heuristically when no embed_fn.
        if self.embed_fn is None:
            scored = self._score_chunks_heuristic(chunks)
        else:
            scored = self._score_chunks_semantic(chunks)

        # Recursively summarize top-scored chunks.
        selected = scored[: min(len(scored), max(3, self.depth))]
        parts: list[str] = []
        for _, chunk in selected:
            sub = self.summarize(chunk, layer=layer + 1)
            parts.append(sub.text)
        result = "\n\n".join(p for p in parts if p.strip())
        if len(result) > budget * 4:
            result = result[: budget * 4]
        return SummaryResult(
            text=result,
            depth_used=self.depth,
            source_length=len(text),
            layer=layer,
        )

    def _budget_for_layer(self, layer: int) -> int:
        """Budget (in tokens) for a given summary layer."""
        return max(50, self.max_tokens_per_layer // (layer + 1))

    def _chunk(self, text: str, max_chars: int = 2000) -> list[str]:
        """Split text into roughly-equal chunks at paragraph/sentence boundaries."""
        if len(text) <= max_chars:
            return [text]
        # Split on paragraphs first; fall back to sentence boundaries.
        parts = re.split(r"\n\n+", text)
        if len(parts) <= 1:
            parts = re.split(r"(?<=[.!?])\s+", text)
        if len(parts) <= 1:
            parts = [text[i : i + max_chars] for i in range(0, len(text), max_chars)]
        # Merge short neighbours.
        merged: list[str] = []
        buf = ""
        for p in parts:
            if len(buf) + len(p) + 2 <= max_chars:
                buf = f"{buf}\n\n{p}" if buf else p
            else:
                if buf:
                    merged.append(buf)
                buf = p
        if buf:
            merged.append(buf)
        return merged

    def _score_chunks_heuristic(self, chunks: list[str]) -> list[tuple[float, str]]:
        """Rank chunks by a heuristic (length + keyword density)."""
        results: list[tuple[float, str]] = []
        for chunk in chunks:
            # Favor longer chunks with multiple sentences.
            sentences = max(1, len(re.findall(r"[.!?]", chunk)))
            score = len(chunk) * 0.5 + sentences * 50
            results.append((score, chunk))
        results.sort(key=lambda x: x[0], reverse=True)
        return results

    def _score_chunks_semantic(self, chunks: list[str]) -> list[tuple[float, str]]:
        """Score chunks using the injected embed_fn (centroid proximity)."""
        try:
            embeddings = [self.embed_fn(c) for c in chunks]  # type: ignore[misc]
            # Centroid.
            dim = len(embeddings[0]) if embeddings else 0
            if dim == 0:
                return self._score_chunks_heuristic(chunks)
            centroid = [0.0] * dim
            for emb in embeddings:
                for i in range(dim):
                    centroid[i] += emb[i]
            centroid = [x / len(embeddings) for x in centroid]
            # Proximity to centroid.
            results = []
            for emb, chunk in zip(embeddings, chunks, strict=False):
                dist = sum((a - b) ** 2 for a, b in zip(emb, centroid, strict=False)) ** 0.5
                results.append((-dist, chunk))  # negative for descending
            results.sort(key=lambda x: x[0], reverse=True)
            return results
        except Exception:
            return self._score_chunks_heuristic(chunks)


# ----------------------------------------------------------------------- #
# Selector-layer integration
# ----------------------------------------------------------------------- #


def get_l2_summary(
    community_id: int,
    store: Any = None,
    *,
    project_path: Any = None,
    max_tokens: int | None = None,
    embed_fn: Callable[[str], list[float]] | None = None,
) -> str:
    """Generate a learned summary for an L2 community.

    Reads community node data via the IR contract (B1), applies
    RAPTOR-style recursive summarization, and returns the result as a
    compact string. Falls back to an empty string (so the selector uses
    its existing L2 retrieval) when ``NEURALMIND_SUMMARIZE`` is not
    enabled, the IR is missing, or the community is empty.
    """
    enabled = os.environ.get("NEURALMIND_SUMMARIZE") == "1"
    if not enabled:
        return ""

    budget = max_tokens or effective_int(project_path, "L2_MAX_TOKENS")

    if store is None or project_path is None:
        return ""

    # B1: IR is the contract for community/node data. Pull from the
    # serialized IR rather than querying nonexistent tables.
    try:
        from pathlib import Path

        from . import ir as ir_mod

        ir_path = ir_mod.project_artifact(Path(project_path), ".neuralmind", "index_ir.json")
        if not ir_path.exists():
            return ""
        index_ir = ir_mod.IndexIR.read(ir_path)
        # IRCluster has no `nodes` attr — filter the flat node list by cluster id.
        cluster_nodes = [n for n in index_ir.nodes if n.cluster == community_id]
        if not cluster_nodes:
            return ""
        parts = [f"### Community {community_id}", ""]
        for ir_node in cluster_nodes:
            # IRNode has no `description` — check the extra dict.
            desc = ir_node.extra.get("description", "") if ir_node.extra else ""
            if desc:
                parts.append(f"- **{ir_node.label}**: {desc}")
            else:
                parts.append(f"- {ir_node.label}")
        text = "\n".join(parts)
    except Exception:
        return ""

    summarizer = RaptorSummarizer(
        depth=DEFAULT_DEPTH,
        max_tokens_per_layer=budget,
        embed_fn=embed_fn,
    )
    result = summarizer.summarize(text, layer=1)
    return result.text if result.text else text[: budget * 4]
