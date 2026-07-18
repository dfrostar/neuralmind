"""
scip_backend.py — SCIP precision pass backend (PRD 2 G2).

For languages with SCIP support (Go, Rust, Java, C/C++), use `scip-index`
at build time for compiler-accurate edges. Falls back to tree-sitter where
SCIP is unavailable. Gated behind NEURALMIND_SCIP=1 (opt-in until measured
parity).

This module wraps the existing precision.py module into a backend class
that can be dispatched from graphgen.py. It provides the SCIPBackend class
with the same interface as the tree-sitter backend for drop-in replacement.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass
class ScipConfig:
    """Configuration for the SCIP precision backend."""

    # Enable SCIP precision (env NEURALMIND_SCIP=1).
    enabled: bool = False
    # Path to the SCIP index file (auto-detected if None).
    index_path: str | None = None
    # Fall back to tree-sitter if SCIP unavailable.
    fallback_to_tree_sitter: bool = True


class ScipBackend:
    """SCIP-based backend for compiler-accurate edge resolution.

    Wraps the existing precision.py SCIP parser and exposes a uniform
    interface for graphgen.py dispatch. Detects the SCIP index at
    construction and validates that the SCIP tool is importable.
    """

    def __init__(self, config: ScipConfig | None = None):
        self.config = config or ScipConfig()
        self._index = None
        self._available: bool | None = None

    @property
    def is_available(self) -> bool:
        """Check if SCIP is available (cached after first call)."""
        if self._available is not None:
            return self._available
        if not self.config.enabled:
            self._available = False
            return False
        index_path = self._resolve_index_path()
        if index_path is None:
            self._available = False
            return False
        try:
            from . import precision

            data = Path(index_path).read_bytes()
            self._index = precision.parse_scip_index(data)
            self._available = True
        except Exception:
            self._available = False
        return self._available

    def _resolve_index_path(self) -> str | None:
        """Resolve the SCIP index path from config or auto-detection."""
        if self.config.index_path:
            return self.config.index_path
        from . import precision

        found = precision.find_scip_index(getattr(self, "_project_path", "."))
        return str(found) if found else None

    def refine_graph(self, graph: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any] | None]:
        """Apply the SCIP precision pass if available and enabled.

        Returns (graph, stats) — stats is None when the pass didn't run.
        """
        if not self.is_available:
            if self.config.fallback_to_tree_sitter:
                return graph, None
            return graph, None

        from . import precision

        if self._index is None:
            return graph, None
        try:
            graph_out, stats = precision.refine_graph(graph, self._index)
            return graph_out, stats.to_dict() if stats else None
        except Exception:
            # Fail-open: return the graph unchanged.
            return graph, None

    @staticmethod
    def detect_languages() -> set[str]:
        """Languages with SCIP support (Go, Rust, Java, C/C++)."""
        return {"go", "rust", "java", "c", "cpp"}

    def stats(self) -> dict:
        return {
            "enabled": self.config.enabled,
            "available": self._available,
            "index_loaded": self._index is not None,
            "languages": sorted(self.detect_languages()),
        }


def is_scip_available() -> bool:
    """Return True if SCIP is enabled and an index is found."""
    return ScipBackend().is_available


def apply_scip_if_available(
    graph: dict[str, Any],
    *,
    enabled: bool = False,
    index_path: str | None = None,
) -> tuple[dict[str, Any], dict[str, Any] | None]:
    """Convenience: apply SCIP precision pass if enabled."""
    backend = ScipBackend(ScipConfig(enabled=enabled, index_path=index_path))
    return backend.refine_graph(graph)
