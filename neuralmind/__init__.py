import os
import warnings
import logging

# Mute ChromaDB telemetry and Pydantic warnings
os.environ["ANONYMIZED_TELEMETRY"] = "False"
os.environ["CHROMA_TELEMETRY"] = "False"
warnings.filterwarnings("ignore", category=DeprecationWarning)
warnings.filterwarnings("ignore", module="chromadb")
warnings.filterwarnings("ignore", module="posthog")

# Suppress posthog logging errors if it still tries to ping
logging.getLogger("posthog").setLevel(logging.ERROR)
logging.getLogger("chromadb.telemetry").setLevel(logging.ERROR)

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
from .embedder import GraphEmbedder

__version__ = "0.1.0"
__all__ = ["NeuralMind", "GraphEmbedder", "ContextSelector"]
