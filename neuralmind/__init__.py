import logging
import os
import warnings

# Mute ChromaDB telemetry and Pydantic warnings.
#
# ChromaDB 0.6.x has a posthog signature mismatch that spams stderr with
# "Failed to send telemetry event ...: capture() takes 1 positional argument
# but 3 were given" on every operation, even when telemetry is disabled via
# Settings(anonymized_telemetry=False). The messages come through logger.error()
# calls, so the loggers must be set to CRITICAL (not ERROR) to suppress them.
os.environ["ANONYMIZED_TELEMETRY"] = "False"
os.environ["CHROMA_TELEMETRY"] = "False"
os.environ["CHROMA_TELEMETRY_DISABLED"] = "1"
warnings.filterwarnings("ignore", category=DeprecationWarning)
warnings.filterwarnings("ignore", module="chromadb")
warnings.filterwarnings("ignore", module="posthog")

# Suppress posthog/chromadb telemetry noise. Must be CRITICAL because the
# "Failed to send telemetry event" messages are emitted as logger.error(),
# and ERROR-level filter lets ERROR messages through.
for _logger_name in (
    "posthog",
    "chromadb.telemetry",
    "chromadb.telemetry.product",
    "chromadb.telemetry.product.posthog",
):
    logging.getLogger(_logger_name).setLevel(logging.CRITICAL)

# Belt-and-suspenders: monkey-patch chromadb's Posthog client capture() to be
# a silent no-op. This defends against any chromadb version where the logger
# hierarchy doesn't propagate as expected.
try:
    from chromadb.telemetry.product.posthog import Posthog as _ChromaPosthog

    def _noop_capture(self, *args, **kwargs):  # pragma: no cover
        return None

    _ChromaPosthog.capture = _noop_capture
except Exception:  # pragma: no cover
    pass

"""
NeuralMind - Adaptive Neural Knowledge System
=============================================

Replaces static Obsidian wiki with dynamic neural knowledge representation.
Builds on graphify output and mempalace's 4-layer architecture.

Key Features:
- Vector embeddings for semantic search
- Intelligent context selection (progressive disclosure)
- Massive token reduction (target: 6-49x as per code-review-graph benchmarks)
- Continuous learning from interactions

Architecture:
- Layer 0: Identity (~100 tokens) - always loaded
- Layer 1: Project Summary (~500 tokens) - always loaded
- Layer 2: On-Demand Context (~200-500 each) - loaded per query
- Layer 3: Deep Search (unlimited) - full semantic search

Token Budget:
- Wake-up cost: ~600-900 tokens (L0+L1)
- Per-query cost: ~200-500 tokens (L2)
- Leaves 95%+ context free for actual work
"""

from .context_selector import ContextSelector
from .core import NeuralMind
from .embedder import KnowledgeSearcher

__version__ = "0.1.0"
__all__ = ["NeuralMind", "KnowledgeSearcher", "ContextSelector"]
