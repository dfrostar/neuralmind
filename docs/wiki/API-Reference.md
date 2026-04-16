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
    print("Run 'graphify update' first to generate knowledge graph")
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
