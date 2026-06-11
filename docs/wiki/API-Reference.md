# API Reference

Complete Python API documentation for NeuralMind.

## Table of Contents

- [Overview](#overview)
- [Quick Start](#quick-start)
- [Core Classes](#core-classes)
  - [NeuralMind](#neuralmind)
  - [ContextResult](#contextresult)
  - [TokenBudget](#tokenbudget)
- [Embedder Module](#embedder-module)
  - [GraphEmbedder](#graphembedder)
- [Context Selector Module](#context-selector-module)
  - [ContextSelector](#contextselector)
- [Synapse Module *(v0.4+, directional v0.11+)*](#synapse-module-v04-directional-v011)
  - [SynapseStore](#synapsestore)
- [Exceptions](#exceptions)
- [Type Hints](#type-hints)
- [Examples](#examples)

---

## Overview

NeuralMind provides a Python API for building neural indexes from code knowledge graphs and querying them with natural language. The API is designed to be simple for common use cases while providing flexibility for advanced usage.

### Module Structure

```
neuralmind/
├── __init__.py          # Main exports: NeuralMind, ContextResult, TokenBudget
├── core.py              # NeuralMind class implementation
├── embedder.py          # GraphEmbedder for vector storage
├── context_selector.py  # ContextSelector for 4-layer context generation
├── cli.py               # Command-line interface
└── mcp_server.py        # MCP server for AI tool integration
```

### Main Exports

```python
from neuralmind import NeuralMind, ContextResult, TokenBudget
```

---

## Quick Start

```python
from neuralmind import NeuralMind

# Initialize for a project
mind = NeuralMind('/path/to/project')

# Build the neural index (required first time)
mind.build()

# Get wake-up context for starting conversations
wakeup = mind.wakeup()
print(f"Context ({wakeup.budget.total} tokens):")
print(wakeup.context)

# Query with natural language
result = mind.query("How does authentication work?")
print(f"\nQuery result ({result.budget.total} tokens, {result.reduction_ratio:.1f}x reduction):")
print(result.context)
```

---

## Core Classes

### NeuralMind

Main interface for neural codebase understanding.

```python
class NeuralMind:
    """Adaptive Neural Knowledge System for AI code understanding."""
```

#### Constructor

```python
def __init__(self, project_path: str, db_path: str = None):
    """
    Initialize NeuralMind for a project.
    
    Args:
        project_path: Path to project root. Must contain:
            - graphify-out/graph.json (knowledge graph)
        db_path: Optional custom path for ChromaDB storage.
            Default: {project_path}/graphify-out/neuralmind_db
    
    Raises:
        FileNotFoundError: If project_path doesn't exist
        ValueError: If project_path is not a directory
    
    Example:
        >>> mind = NeuralMind('/home/user/myproject')
        >>> mind = NeuralMind('/home/user/myproject', db_path='/tmp/custom_db')
    """
```

#### Methods

##### build

```python
def build(self, force: bool = False) -> Dict[str, Any]:
    """
    Build neural index from graph.json.
    
    Generates embeddings for all nodes in the knowledge graph and
    stores them in ChromaDB for semantic search.
    
    Args:
        force: If True, re-embed all nodes even if unchanged.
            Default False uses incremental updates.
    
    Returns:
        Dict with build statistics:
        {
            'nodes_processed': int,      # Total nodes in graph
            'nodes_embedded': int,       # Nodes that were embedded
            'nodes_skipped': int,        # Unchanged nodes skipped
            'communities': int,          # Number of code clusters
            'time_elapsed': float,       # Build time in seconds
            'embedding_model': str,      # Model used for embeddings
        }
    
    Raises:
        FileNotFoundError: If graph.json not found
        RuntimeError: If embedding generation fails
    
    Example:
        >>> stats = mind.build()
        >>> print(f"Processed {stats['nodes_processed']} nodes in {stats['time_elapsed']:.2f}s")
        
        >>> # Force complete rebuild
        >>> stats = mind.build(force=True)
    """
```

##### wakeup

```python
def wakeup(self) -> ContextResult:
    """
    Get minimal wake-up context for starting a conversation.
    
    Loads only L0 (Identity) + L1 (Summary) layers, providing
    essential project context with minimal token usage (~600 tokens).
    
    Ideal for:
        - Starting new AI conversations
        - System prompts for coding assistants
        - Quick project overviews
    
    Returns:
        ContextResult with wake-up context
    
    Raises:
        RuntimeError: If index not built (call build() first)
    
    Example:
        >>> wakeup = mind.wakeup()
        >>> print(f"Tokens: {wakeup.budget.total}")
        >>> print(wakeup.context)
    """
```

##### query

```python
def query(self, question: str) -> ContextResult:
    """
    Get optimized context for a specific question.
    
    Loads all 4 layers with query-relevant content:
        - L0: Project identity
        - L1: Architecture summary
        - L2: Relevant modules based on query
        - L3: Semantic search results
    
    Args:
        question: Natural language question about the codebase
    
    Returns:
        ContextResult with optimized context (~1000-1500 tokens)
    
    Raises:
        RuntimeError: If index not built
        ValueError: If question is empty
    
    Example:
        >>> result = mind.query("How does authentication work?")
        >>> print(f"Reduction: {result.reduction_ratio:.1f}x")
        >>> print(result.context)
    """
```

##### search

```python
def search(
    self,
    query: str,
    n: int = 10,
    node_type: str = None,
    community: int = None,
    min_score: float = 0.0
) -> List[Dict[str, Any]]:
    """
    Direct semantic search across codebase entities.
    
    Args:
        query: Semantic search query
        n: Maximum number of results (default: 10)
        node_type: Filter by node type ('function', 'class', 'file', etc.)
        community: Filter by community/cluster ID
        min_score: Minimum similarity score threshold (0.0-1.0)
    
    Returns:
        List of matching entities, each containing:
        {
            'id': str,              # Unique node identifier
            'name': str,            # Entity name
            'type': str,            # Node type
            'file_path': str,       # Source file path
            'description': str,     # Brief description
            'community': int,       # Cluster membership
            'score': float,         # Similarity score (0-1)
        }
    
    Raises:
        RuntimeError: If index not built
    
    Example:
        >>> results = mind.search("authentication", n=5)
        >>> for r in results:
        ...     print(f"{r['name']} ({r['type']}): {r['score']:.2f}")
        
        >>> # Filter by type
        >>> functions = mind.search("validate", node_type='function')
    """
```

##### benchmark

```python
def benchmark(self, sample_queries: List[str] = None) -> Dict[str, Any]:
    """
    Run performance benchmark with sample queries.
    
    Args:
        sample_queries: Optional list of custom queries.
            Uses default set if not provided:
            - "How does authentication work?"
            - "What are the main API endpoints?"
            - "Explain the database models"
    
    Returns:
        Dict with benchmark results:
        {
            'project_name': str,
            'total_nodes': int,
            'communities': int,
            'estimated_full_tokens': int,
            'results': [
                {
                    'query': str,
                    'tokens': int,
                    'reduction': float,
                    'latency_ms': float,
                },
                ...
            ],
            'averages': {
                'tokens': float,
                'reduction': float,
                'latency_ms': float,
            },
            'total_time_ms': float,
        }
    
    Example:
        >>> results = mind.benchmark()
        >>> print(f"Average reduction: {results['averages']['reduction']:.1f}x")
        
        >>> # Custom queries
        >>> results = mind.benchmark(["How does caching work?", "Explain the auth flow"])
    """
```

##### export_context

```python
def export_context(
    self,
    query: str = None,
    output_path: str = None
) -> str:
    """
    Export context to file or return as string.
    
    Args:
        query: Optional query. If None, exports wake-up context.
        output_path: Optional file path to write context.
            If None, returns context as string.
    
    Returns:
        Context string, or path to exported file if output_path provided.
    
    Example:
        >>> # Get as string
        >>> context = mind.export_context("How does auth work?")
        
        >>> # Export to file
        >>> path = mind.export_context(output_path="context.md")
    """
```

##### get_stats

```python
def get_stats(self) -> Dict[str, Any]:
    """
    Get statistics about the neural index.
    
    Returns:
        Dict with index statistics:
        {
            'project_name': str,
            'graph_path': str,
            'db_path': str,
            'node_count': int,
            'edge_count': int,
            'community_count': int,
            'node_types': Dict[str, int],  # Count by type
            'embedding_dimensions': int,
            'index_size_bytes': int,
            'last_build': str,             # ISO timestamp
            'build_duration': float,       # Seconds
        }
    
    Example:
        >>> stats = mind.get_stats()
        >>> print(f"Nodes: {stats['node_count']}")
        >>> print(f"Communities: {stats['community_count']}")
    """
```

---

### ContextResult

Result of context generation.

```python
from dataclasses import dataclass
from typing import List

@dataclass
class ContextResult:
    """Result of context generation operations."""
    
    context: str
    """The optimized context text ready for AI consumption."""
    
    budget: TokenBudget
    """Token usage breakdown by layer."""
    
    layers_used: List[str]
    """Which layers were loaded (e.g., ['L0', 'L1', 'L2', 'L3'])."""
    
    communities_loaded: List[int]
    """IDs of code clusters/communities that were accessed."""
    
    search_hits: int
    """Number of semantic search results included."""
    
    reduction_ratio: float
    """Token reduction compared to full codebase.
    
    Example: 50.0 means 50x reduction (2% of original size).
    """
```

#### Usage Example

```python
result = mind.query("How does authentication work?")

# Access context
print(result.context)

# Check token usage
print(f"Total tokens: {result.budget.total}")
print(f"L0: {result.budget.l0}, L1: {result.budget.l1}")
print(f"L2: {result.budget.l2}, L3: {result.budget.l3}")

# Check what was loaded
print(f"Layers: {result.layers_used}")
print(f"Communities: {result.communities_loaded}")
print(f"Search hits: {result.search_hits}")

# Token reduction
print(f"Reduction: {result.reduction_ratio:.1f}x")
```

---

### TokenBudget

Token usage tracking across layers.

```python
from dataclasses import dataclass

@dataclass
class TokenBudget:
    """Token usage tracking across layers."""
    
    l0: int
    """Identity layer tokens (~100)."""
    
    l1: int
    """Summary layer tokens (~500)."""
    
    l2: int
    """On-demand layer tokens (variable)."""
    
    l3: int
    """Search layer tokens (variable)."""
    
    total: int
    """Total tokens used (l0 + l1 + l2 + l3)."""
```

#### Usage Example

```python
result = mind.query("How does the API work?")
budget = result.budget

print(f"Token breakdown:")
print(f"  L0 (Identity): {budget.l0}")
print(f"  L1 (Summary):  {budget.l1}")
print(f"  L2 (Context):  {budget.l2}")
print(f"  L3 (Search):   {budget.l3}")
print(f"  Total:         {budget.total}")
```

---

## Embedder Module

### GraphEmbedder

Handles embedding generation and vector storage.

```python
from neuralmind.embedder import GraphEmbedder

class GraphEmbedder:
    """Generates and manages embeddings for knowledge graph nodes."""
    
    def __init__(self, project_path: str, db_path: str = None):
        """
        Initialize the embedder.
        
        Args:
            project_path: Path to project root
            db_path: Optional custom ChromaDB path
        """
    
    def load_graph(self) -> Dict[str, Any]:
        """
        Load knowledge graph from graph.json.
        
        Returns:
            Parsed graph data with nodes, edges, communities
        """
    
    def embed_nodes(self, force: bool = False) -> Dict[str, int]:
        """
        Generate embeddings for all nodes.
        
        Args:
            force: Re-embed all nodes if True
        
        Returns:
            Dict with embedding statistics
        """
    
    def search(
        self,
        query: str,
        n: int = 10,
        where: Dict = None
    ) -> List[Dict]:
        """
        Semantic search across embedded nodes.
        
        Args:
            query: Search query
            n: Max results
            where: ChromaDB filter conditions
        
        Returns:
            List of matching nodes with scores
        """
```

---

## Context Selector Module

### ContextSelector

Implements the 4-layer progressive disclosure architecture.

```python
from neuralmind.context_selector import ContextSelector

class ContextSelector:
    """Selects optimal context using 4-layer progressive disclosure."""
    
    def __init__(self, embedder: GraphEmbedder, graph_data: Dict):
        """
        Initialize context selector.
        
        Args:
            embedder: GraphEmbedder instance for search
            graph_data: Loaded knowledge graph data
        """
    
    def get_l0_identity(self) -> Tuple[str, int]:
        """
        Get Layer 0: Project identity.
        
        Returns:
            Tuple of (context_text, token_count)
        """
    
    def get_l1_summary(self) -> Tuple[str, int]:
        """
        Get Layer 1: Architecture summary.
        
        Returns:
            Tuple of (context_text, token_count)
        """
    
    def get_l2_context(self, query: str) -> Tuple[str, int, List[int]]:
        """
        Get Layer 2: Query-relevant modules.
        
        Args:
            query: User's question
        
        Returns:
            Tuple of (context_text, token_count, communities_loaded)
        """
    
    def get_l3_search(self, query: str, n: int = 10) -> Tuple[str, int, int]:
        """
        Get Layer 3: Semantic search results.
        
        Args:
            query: Search query
            n: Max results
        
        Returns:
            Tuple of (context_text, token_count, hit_count)
        """
    
    def get_wakeup_context(self) -> ContextResult:
        """
        Get wake-up context (L0 + L1).
        
        Returns:
            ContextResult with minimal context
        """
    
    def get_query_context(self, query: str) -> ContextResult:
        """
        Get full query context (L0 + L1 + L2 + L3).
        
        Args:
            query: User's question
        
        Returns:
            ContextResult with optimized context
        """
```

---

## Synapse Module *(v0.4+, directional v0.11+)*

The synapse layer is a brain-like associative memory that runs alongside
the LLM. Two parallel signals:

- **Undirected co-activation** *(v0.4+)* — symmetric Hebbian edges over
  nodes that fire together. Powers spreading-activation recall.
- **Directional transitions** *(v0.11+)* — ordered `(from_node, to_node)`
  observations. Answers "what typically follows what." Surfaces as
  `next_likely()`, the `neuralmind next` CLI, the
  `neuralmind_next_likely` MCP tool, and the "What typically comes next"
  section of the auto-generated `SYNAPSE_MEMORY.md`.

```python
from neuralmind import SynapseStore, default_db_path

store = SynapseStore(default_db_path("/path/to/repo"))
```

### SynapseStore

SQLite-backed weighted graph at `<project>/.neuralmind/synapses.db`.
Safe to construct lazily and share across hooks; each call opens a
short-lived connection so the file watcher and MCP server can both
write without pinning a handle.

#### Constructor

```python
SynapseStore(db_path: str | Path)
```

| Parameter | Type | Description |
|-----------|------|-------------|
| `db_path` | `str \| Path` | Path to the SQLite file. Parent dirs are created. |

#### Methods — undirected co-activation *(v0.4+)*

```python
def reinforce(
    node_ids: Iterable[str],
    strength: float = 1.0,
    now: float | None = None,
) -> int
```

Hebbian update: bumps weights on every pairwise edge among
`node_ids`. Self-pairs and duplicates ignored. Returns the number
of pairs touched.

```python
def neighbors(node_id: str, k: int = 5) -> list[tuple[str, float]]
```

Top-k strongest undirected neighbors.

```python
def spread(
    seeds: Iterable[tuple[str, float]] | Iterable[str],
    depth: int = 2,
    top_k: int = 12,
) -> list[tuple[str, float]]
```

Spreading activation over the undirected graph. Returns `(node, activation)`
pairs ranked by accumulated energy, with hub normalization to prevent
runaway central nodes from dominating.

#### Methods — directional transitions *(v0.11+)*

```python
def record_sequence(
    ordered_ids: Iterable[str],
    strength: float = 1.0,
    now: float | None = None,
) -> int
```

Record an ordered sequence as directional transitions. For each
consecutive distinct pair `(a, b)`, bump the `a -> b` weight. Self-
transitions and consecutive duplicates are collapsed. The store accepts
any string keys — file paths, node ids, route names — callers pick
the granularity.

Returns the number of transition rows touched.

```python
def next_likely(
    from_node: str,
    top_k: int = 5,
) -> list[tuple[str, float]]
```

Returns the top successors of `from_node` as `(to_node, probability)`
pairs. Probabilities normalize over **all** outgoing transitions from
`from_node` and sum to 1.0 across the full distribution (the returned
top-k may sum to less).

Returns `[]` when `from_node` has no recorded transitions.

```python
def transitions(
    from_node: str | None = None,
    min_weight: float = 0.0,
    limit: int = 2000,
) -> list[tuple[str, str, float, int]]
```

Raw read-only listing of `(from, to, weight, count)` rows. Strongest
first. Filter by `from_node` for a single source, omit for the full
table. Used by the graph-view UI to overlay directional edges.

#### Methods — lifecycle

```python
def decay(now: float | None = None) -> dict
```

Multiplicatively shrink all weights — undirected and transitions both.
Returns counts of decayed and pruned edges for each signal:

```python
{
    "pruned": int,                  # undirected edges pruned
    "remaining": int,               # undirected edges remaining
    "pruned_transitions": int,      # transitions pruned (v0.11+)
    "remaining_transitions": int,   # transitions remaining (v0.11+)
}
```

```python
def stats() -> dict
def reset() -> None
def normalize_hubs(max_degree: int = 50) -> int
def edges(min_weight: float = 0.0, limit: int = 2000) -> list[tuple[str, str, float, int]]
```

#### Example: directional prediction

```python
from neuralmind import SynapseStore, default_db_path

store = SynapseStore(default_db_path("/path/to/repo"))

# Record several editing sessions — record_sequence captures only
# *consecutive* pairs, so [A, B, C] records A->B and B->C, not A->C.
for _ in range(3):
    store.record_sequence(["src/auth/handlers.py", "tests/test_auth.py"])
store.record_sequence(["src/auth/handlers.py", "src/auth/middleware.py"])

# Predict what follows handlers.py
for to_node, prob in store.next_likely("src/auth/handlers.py"):
    print(f"{prob*100:5.1f}%  {to_node}")
# Output:
#  75.0%  tests/test_auth.py
#  25.0%  src/auth/middleware.py
```

---

## Exceptions

```python
class NeuralMindError(Exception):
    """Base exception for NeuralMind errors."""
    pass

class GraphNotFoundError(NeuralMindError):
    """Raised when graph.json is not found."""
    pass

class IndexNotBuiltError(NeuralMindError):
    """Raised when operations require a built index."""
    pass

class EmbeddingError(NeuralMindError):
    """Raised when embedding generation fails."""
    pass
```

---

## Type Hints

```python
from typing import Dict, List, Any, Optional, Tuple
from pathlib import Path

# Common type aliases used in the API
NodeDict = Dict[str, Any]
GraphData = Dict[str, Any]
SearchResult = Dict[str, Any]
BenchmarkResult = Dict[str, Any]
StatsResult = Dict[str, Any]
```

---

## Examples

### Basic Usage

```python
from neuralmind import NeuralMind

# Initialize
mind = NeuralMind('/path/to/project')

# Build index
mind.build()

# Query
result = mind.query("How does the payment system work?")
print(result.context)
```

### Integration with AI APIs

```python
import openai
from neuralmind import NeuralMind

# Get optimized context
mind = NeuralMind('/path/to/project')
mind.build()

context = mind.query("How does authentication work?").context

# Use with OpenAI
response = openai.chat.completions.create(
    model="gpt-4",
    messages=[
        {"role": "system", "content": f"You are helping with this codebase:\n\n{context}"},
        {"role": "user", "content": "How can I add OAuth support?"}
    ]
)
```

### Batch Processing

```python
from neuralmind import NeuralMind

projects = [
    '/path/to/project1',
    '/path/to/project2',
    '/path/to/project3',
]

for project in projects:
    mind = NeuralMind(project)
    stats = mind.build()
    print(f"{project}: {stats['nodes_processed']} nodes")
```

### Custom Token Budgets

```python
from neuralmind import NeuralMind
from neuralmind.context_selector import ContextSelector

# Note: Custom budgets require direct access to ContextSelector
mind = NeuralMind('/path/to/project')
mind.build()

# Access the selector for advanced configuration
selector = mind._context_selector

# Modify token limits (if supported by implementation)
# selector.set_budget('l1', 300)  # Reduce L1 budget
# selector.set_budget('l2', 800)  # Increase L2 budget
```

### Error Handling

```python
from neuralmind import NeuralMind
from neuralmind.core import GraphNotFoundError, IndexNotBuiltError

try:
    mind = NeuralMind('/path/to/project')
    result = mind.query("How does auth work?")
except GraphNotFoundError:
    print("Run 'neuralmind build' first to generate the knowledge graph")
except IndexNotBuiltError:
    print("Run mind.build() before querying")
except Exception as e:
    print(f"Unexpected error: {e}")
```

### Async Usage (Future)

```python
# Note: Async API may be available in future versions
import asyncio
from neuralmind import AsyncNeuralMind  # Hypothetical

async def process_queries():
    mind = AsyncNeuralMind('/path/to/project')
    await mind.build()
    
    queries = [
        "How does auth work?",
        "What are the API endpoints?",
        "Explain the database schema"
    ]
    
    results = await asyncio.gather(*[
        mind.query(q) for q in queries
    ])
    
    for query, result in zip(queries, results):
        print(f"{query}: {result.budget.total} tokens")
```

---

## See Also

- [CLI Reference](CLI-Reference.md) - Command-line interface
- [Architecture](Architecture.md) - System design details
- [Integration Guide](Integration-Guide.md) - MCP and tool integrations
