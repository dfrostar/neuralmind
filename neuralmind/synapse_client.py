"""synapse_client.py — Hebbian synapse operations.

Wraps SynapseStore with file-level convenience, compliance detection,
and activity-based co-activation. Extracted from NeuralMind to keep
the orchestrator thin.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING

from .synapses import SynapseStore

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


def _compliance_synapse_key(control_id: str, framework: str) -> str:
    """Build the synapse node key for a compliance control."""
    return f"compliance:{framework}:{control_id}"


class SynapseClient:
    """Thin orchestration over SynapseStore for file/activity-level ops."""

    def __init__(self, store: SynapseStore | None, project_path: Path) -> None:
        self.store = store
        self.project_path = project_path

    def has_store(self) -> bool:
        return self.store is not None

    # ── Activation ─────────────────────────────────────────────────────────

    def activate(self, node_ids: list[str], strength: float = 1.0) -> int:
        """Reinforce a set of node ids."""
        if not self.store or not node_ids:
            return 0
        try:
            return self.store.reinforce(node_ids, strength=strength)
        except Exception:
            logger.debug("synapse activate failed", exc_info=True)
            return 0

    def deactivate(self, node_ids: list[str]) -> int:
        """Decay a set of node ids."""
        if not self.store or not node_ids:
            return 0
        try:
            return self.store.decay(node_ids)
        except Exception:
            logger.debug("synapse deactivate failed", exc_info=True)
            return 0

    def reinforce_files(self, file_paths: list[str], nodes: list[dict], strength: float = 1.0) -> int:
        """Reinforce every node belonging to the given files."""
        ids = [
            str(n["id"]) for n in nodes
            if n.get("source_file") in file_paths
        ]
        return self.activate(ids, strength=strength)

    # ── Spread / recall ────────────────────────────────────────────────────

    def spread(self, seed_ids: list[str], depth: int = 2, top_k: int = 8) -> list[tuple[str, float]]:
        """Spread activation from seeds. Empty on cold graph."""
        if not self.store or not seed_ids:
            return []
        try:
            return self.store.spread(seed_ids, depth=depth, top_k=top_k)
        except Exception:
            logger.debug("synapse spread failed", exc_info=True)
            return []

    def spread_detailed(
        self, seed_ids: list[str], depth: int = 2, top_k: int = 8
    ) -> tuple[list[tuple[str, float]], dict[str, dict[str, float]]]:
        """Spread with per-namespace attribution."""
        if not self.store or not seed_ids:
            return [], {}
        try:
            return self.store.spread_with_contributions(seed_ids, depth=depth, top_k=top_k)
        except Exception:
            logger.debug("synapse spread_detailed failed", exc_info=True)
            return [], {}

    def synaptic_neighbors(self, node_id: str, depth: int = 1, top_k: int = 8) -> list[tuple[str, float]]:
        """Get learned neighbors for a single node."""
        return self.spread([node_id], depth=depth, top_k=top_k)

    # ── Compliance ────────────────────────────────────────────────────────

    def detect_compliance(self, file_paths: list[str], nodes: list[dict]) -> list[dict]:
        """Match code files against CMMC controls and reinforce hits."""
        if not self.store:
            return []

        results = []
        for fp in file_paths:
            file_node_ids = []
            try:
                for node in nodes or []:
                    if node.get("source_file", "") == fp or str(
                        node.get("source_file", "")
                    ).startswith(str(Path(fp).relative_to(self.project_path))):
                        nid = node.get("id")
                        if nid:
                            file_node_ids.append(str(nid))
            except Exception:
                logger.debug("compliance: file node lookup failed for %s", fp, exc_info=True)
                continue

            if not file_node_ids:
                continue

            # Heuristic match (placeholder — real impl would use pattern matching)
            matches = []  # In real impl: _match_controls(fp, content)
            for match in matches:
                ctrl_id = match["control_id"]
                framework = match["framework"]
                syn_key = _compliance_synapse_key(ctrl_id, framework)
                try:
                    self.store.reinforce(file_node_ids + [syn_key], strength=0.8)
                except Exception:
                    logger.debug("compliance: reinforce failed", exc_info=True)
                results.append({
                    "file": fp,
                    "control_id": ctrl_id,
                    "framework": framework,
                    "label": match.get("label", ""),
                })

        return results

    # ── Stats / export ────────────────────────────────────────────────────

    def stats(self) -> dict | None:
        if not self.store:
            return None
        try:
            return self.store.stats()
        except Exception:
            logger.debug("synapse stats failed", exc_info=True)
            return None

    def edges(self, min_weight: float = 0.0, limit: int = 5000) -> list[tuple[str, str, float]]:
        if not self.store:
            return []
        try:
            return self.store.edges(min_weight=min_weight, limit=limit)
        except Exception:
            logger.debug("synapse edges failed", exc_info=True)
            return []
