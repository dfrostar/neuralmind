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
# and ERROR-level filter lets ERROR messages through. Setting logger levels +
# env vars here is import-free (no chromadb dependency); the actual posthog
# monkey-patch happens lazily inside ``embedder`` when the chroma backend is
# constructed, so merely importing ``neuralmind`` no longer pulls in ChromaDB.
# See ``embedder._silence_chroma_telemetry``.
for _logger_name in (
    "posthog",
    "chromadb.telemetry",
    "chromadb.telemetry.product",
    "chromadb.telemetry.product.posthog",
):
    logging.getLogger(_logger_name).setLevel(logging.CRITICAL)

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

from .audit import AuditTrail
from .backend_manager import BackendManager
from .compressors import (
    cap_search_results,
    compress_bash,
    compress_read,
    offload_if_large,
)
from .context_selector import ContextSelector
from .core import NeuralMind, validate_project
from .embedding_backend import EmbeddingBackend
from .hooks import install_hooks
from .in_memory_backend import InMemoryEmbeddingBackend
from .ir import (
    IR_VERSION,
    SYNAPSE_BUNDLE_VERSION,
    IndexIR,
    IRCluster,
    IREdge,
    IRError,
    IRNode,
    IRSynapse,
    export_synapse_bundle,
    from_graph_json,
    import_synapse_bundle,
    to_graph_json,
    validate_ir,
    validate_synapse_bundle,
)
from .namespaces import resolve_namespace
from .synapse_memory import (
    export_synapse_memory,
    project_memory_file,
    render_synapse_memory,
)
from .synapses import (
    DEFAULT_NAMESPACE,
    EPHEMERAL_NAMESPACE,
    SHARED_NAMESPACE,
    SynapseStore,
    default_db_path,
)
from .team_memory import (
    TEAM_BUNDLE_FILENAME,
    build_team_bundle,
    maybe_import_team_memory,
    publish_team_memory,
    team_bundle_path,
)
from .trace import RetrievalTrace
from .watcher import FileActivityWatcher

__version__ = "0.34.0"
# NOTE: ``GraphEmbedder`` is intentionally NOT in ``__all__``. It is the
# ChromaDB backend (lazy-exposed via ``__getattr__`` below), and ChromaDB is an
# opt-in extra as of v0.29.0. Listing it in ``__all__`` would make
# ``from neuralmind import *`` resolve the lazy attribute and import ChromaDB,
# which fails on the default ChromaDB-free install. Explicit
# ``from neuralmind import GraphEmbedder`` still works when ``[chromadb]`` is
# installed.
__all__ = [
    "NeuralMind",
    "InMemoryEmbeddingBackend",
    "EmbeddingBackend",
    "ContextSelector",
    "AuditTrail",
    "BackendManager",
    "InMemoryEmbeddingBackend",
    # Output compression (v0.2.0)
    # Brain-like learning (v0.3.0)
    "compress_bash",
    "compress_read",
    "cap_search_results",
    "offload_if_large",
    "install_hooks",
    # Associative synapse layer (v0.4.0)
    "SynapseStore",
    "FileActivityWatcher",
    "default_db_path",
    "render_synapse_memory",
    "export_synapse_memory",
    "project_memory_file",
    # Canonical versioned IR contract (v0.23.0 — PRD 1)
    "IndexIR",
    "IRNode",
    "IREdge",
    "IRCluster",
    "IRSynapse",
    "IRError",
    "IR_VERSION",
    "from_graph_json",
    "to_graph_json",
    "validate_ir",
    "validate_project",
    # Retrieval traces (v0.23.0 — PRD 3)
    "RetrievalTrace",
    # Memory namespaces (PRD 4)
    "DEFAULT_NAMESPACE",
    "SHARED_NAMESPACE",
    "EPHEMERAL_NAMESPACE",
    "resolve_namespace",
    "SYNAPSE_BUNDLE_VERSION",
    "export_synapse_bundle",
    "import_synapse_bundle",
    "validate_synapse_bundle",
    # Team memory (v0.30.0)
    "TEAM_BUNDLE_FILENAME",
    "team_bundle_path",
    "build_team_bundle",
    "publish_team_memory",
    "maybe_import_team_memory",
]


def __getattr__(name: str):
    """Lazily expose ``GraphEmbedder`` without importing ChromaDB at package load.

    ``GraphEmbedder`` lives in :mod:`neuralmind.embedder`, which imports ChromaDB
    at module level. Importing it eagerly here would make ``import neuralmind``
    require ChromaDB — the exact coupling v0.22 removes so the package (and the
    ChromaDB-free ``turbovec`` backend) can run without it. PEP 562 module-level
    ``__getattr__`` keeps ``from neuralmind import GraphEmbedder`` working for
    back-compat while deferring the (ChromaDB-pulling) import to first access.
    """
    if name == "GraphEmbedder":
        from .embedder import GraphEmbedder

        return GraphEmbedder
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
