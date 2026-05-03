# Architecture

Deep dive into NeuralMind's 4-layer progressive disclosure system and technical architecture.

## Table of Contents

- [Overview](#overview)
- [Design Principles](#design-principles)
- [4-Layer Progressive Disclosure](#4-layer-progressive-disclosure)
  - [Layer 0: Identity](#layer-0-identity)
  - [Layer 1: Summary](#layer-1-summary)
  - [Layer 2: On-Demand](#layer-2-on-demand)
  - [Layer 3: Search](#layer-3-search)
- [Data Flow](#data-flow)
- [Component Architecture](#component-architecture)
- [Token Budget Management](#token-budget-management)
- [Embedding Strategy](#embedding-strategy)
- [Community Detection](#community-detection)
- [Performance Optimization](#performance-optimization)

---

## Overview

NeuralMind is designed to solve a fundamental problem in AI-assisted coding: **context window limitations**. When working with AI coding assistants, loading an entire codebase can consume 50,000+ tokens, leaving little room for meaningful conversation.

NeuralMind achieves **40-70x token reduction** through intelligent, query-aware context selection using a 4-layer progressive disclosure architecture.

### The Problem

```
┌─────────────────────────────────────────────────────────────────┐
│                    TRADITIONAL APPROACH                          │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Full Codebase ──────────────────────────────────► AI Context    │
│  (50,000+ tokens)                                (50,000 tokens) │
│                                                                  │
│  Problems:                                                       │
│  • Exceeds context windows                                       │
│  • Most content irrelevant to query                              │
│  • Expensive (token costs)                                       │
│  • Slow processing                                               │
│  • Dilutes important information                                 │
└─────────────────────────────────────────────────────────────────┘
```

### The Solution

```
┌─────────────────────────────────────────────────────────────────┐
│                    NEURALMIND APPROACH                           │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Full Codebase ────► Knowledge ────► Progressive ────► AI Context│
│  (50,000+ tokens)    Graph          Disclosure      (1,000 tokens)│
│                                                                  │
│  Benefits:                                                       │
│  • 40-70x token reduction                                        │
│  • Query-relevant content only                                   │
│  • Cost effective                                                │
│  • Fast response                                                 │
│  • Focused, relevant context                                     │
└─────────────────────────────────────────────────────────────────┘
```

---

## Design Principles

### 1. Progressive Disclosure

Load information incrementally, starting with the most essential and adding detail as needed.

```
Essential (Always)     ──► Identity + Summary    (~600 tokens)
Query-Relevant (Dynamic) ──► Modules + Search    (~400-900 tokens)
                           ─────────────────────
                           Total: ~1000-1500 tokens
```

### 2. Semantic Understanding

Use embeddings and semantic search rather than keyword matching to find relevant code.

### 3. Community Awareness

Leverage code structure and relationships (communities/clusters) to load logically related code together.

### 4. Incremental Updates

Only re-process changed nodes to minimize rebuild time.

### 5. Token Budget Discipline

Strict token limits per layer ensure consistent, predictable context sizes.

---

## 4-Layer Progressive Disclosure

```
┌─────────────────────────────────────────────────────────────────┐
│                    LAYER ARCHITECTURE                            │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │  L0: IDENTITY LAYER                        (~100 tokens) │    │
│  │                                                          │    │
│  │  • Project name                                          │    │
│  │  • Brief description                                     │    │
│  │  • Key facts (language, framework, purpose)              │    │
│  │                                                          │    │
│  │  Source: mempalace.yaml > CLAUDE.md > README.md          │    │
│  │  Loading: ALWAYS                                         │    │
│  └─────────────────────────────────────────────────────────┘    │
│                              │                                   │
│                              ▼                                   │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │  L1: SUMMARY LAYER                         (~500 tokens) │    │
│  │                                                          │    │
│  │  • High-level architecture overview                      │    │
│  │  • Main components and their roles                       │    │
│  │  • Code cluster summaries                                │    │
│  │  • Key patterns and conventions                          │    │
│  │                                                          │    │
│  │  Source: graph.json communities + descriptions           │    │
│  │  Loading: ALWAYS                                         │    │
│  └─────────────────────────────────────────────────────────┘    │
│                              │                                   │
│                              ▼                                   │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │  L2: ON-DEMAND LAYER                   (~200-500 tokens) │    │
│  │                                                          │    │
│  │  • Specific modules relevant to query                    │    │
│  │  • Community/cluster details                             │    │
│  │  • Function signatures and docstrings                    │    │
│  │  • Class hierarchies                                     │    │
│  │                                                          │    │
│  │  Source: Semantic search → community expansion           │    │
│  │  Loading: PER QUERY                                      │    │
│  └─────────────────────────────────────────────────────────┘    │
│                              │                                   │
│                              ▼                                   │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │  L3: SEARCH LAYER                      (~200-500 tokens) │    │
│  │                                                          │    │
│  │  • Semantic search results                               │    │
│  │  • Relevant code snippets                                │    │
│  │  • Direct matches to query terms                         │    │
│  │  • Related entities                                      │    │
│  │                                                          │    │
│  │  Source: ChromaDB vector search                          │    │
│  │  Loading: PER QUERY                                      │    │
│  └─────────────────────────────────────────────────────────┘    │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### Layer 0: Identity

**Purpose**: Establish basic project context that AI needs for any interaction.

**Token Budget**: ~100 tokens

**Content**:
- Project name
- One-paragraph description
- Primary language/framework
- Key purpose or domain

**Source Priority**:
1. `mempalace.yaml` - Structured project metadata
2. `CLAUDE.md` - AI-specific project description
3. `README.md` - Standard project documentation

**Example Output**:
```markdown
# Project: MyApp

MyApp is a full-stack task management application built with React and Node.js. 
It provides real-time collaboration features and integrates with popular 
productivity tools.
```

### Layer 1: Summary

**Purpose**: Provide architectural overview and main component understanding.

**Token Budget**: ~500 tokens

**Content**:
- Architecture overview
- Main modules/packages
- Code cluster summaries
- Key patterns used

**Source**: Generated from `graph.json` community analysis

**Example Output**:
```markdown
## Architecture Overview

### Core Components
- **Frontend** (React 18): Single-page application with TypeScript
- **Backend** (Node.js/Express): REST API with WebSocket support
- **Database** (PostgreSQL): Relational data with Prisma ORM

### Main Modules
1. **User Management** (users/) - Authentication, profiles, permissions
2. **Task Engine** (tasks/) - CRUD, scheduling, notifications
3. **Collaboration** (collab/) - Real-time sync, comments, sharing
4. **API Layer** (api/) - Routes, middleware, validation
```

### Layer 2: On-Demand

**Purpose**: Load specific modules and code clusters relevant to the current query.

**Token Budget**: ~200-500 tokens (variable based on relevance)

**Content**:
- Relevant community/cluster details
- Function signatures and brief docstrings
- Class definitions and relationships
- Module-level documentation

**Selection Process**:
1. Semantic search to find relevant nodes
2. Identify communities containing those nodes
3. Load community summaries and key entities
4. Expand to related communities if budget allows

**Example Output** (for query "How does authentication work?"):
```markdown
## Authentication Module (users/auth/)

### Key Components

**authenticate_user(credentials)** → User | None
  Validates credentials against database, returns user on success.

**generate_jwt(user)** → str
  Creates JWT token with user claims and 24h expiry.

**AuthMiddleware**
  Express middleware that validates JWT and attaches user to request.

### Dependencies
- bcrypt for password hashing
- jsonwebtoken for JWT operations
- Redis for token blacklisting
```

### Layer 3: Search

**Purpose**: Provide direct semantic search results for specific query terms.

**Token Budget**: ~200-500 tokens (variable based on results)

**Content**:
- Top semantic search matches
- Code snippets with context
- Entity descriptions
- File paths and locations

**Search Strategy**:
1. Embed query using same model as index
2. Vector similarity search in ChromaDB
3. Rank by relevance score
4. Filter duplicates from L2
5. Format top N results

**Example Output** (for query "How does authentication work?"):
```markdown
## Search Results

**1. authenticate_user** (function) - Score: 0.92
   `users/auth/handlers.py:45`
   Main authentication handler that validates credentials.

**2. verify_jwt** (function) - Score: 0.88
   `users/auth/jwt.py:23`
   Verifies and decodes JWT tokens.

**3. hash_password** (function) - Score: 0.81
   `users/auth/crypto.py:12`
   Securely hashes passwords using bcrypt.
```

---

## Data Flow

```
┌──────────────────────────────────────────────────────────────────────────┐
│                           DATA FLOW                                       │
└──────────────────────────────────────────────────────────────────────────┘

                              BUILD PHASE
    ┌─────────────┐                                    ┌─────────────┐
    │             │     graphify update                │             │
    │  Codebase   │ ─────────────────────────────────► │ graph.json  │
    │             │     (Parse, Analyze)               │             │
    │  .py .js    │                                    │  Nodes      │
    │  .ts .java  │                                    │  Edges      │
    └─────────────┘                                    │  Communities│
                                                       └──────┬──────┘
                                                              │
                                                              ▼
                                                       ┌─────────────┐
                                                       │             │
                        neuralmind build               │  ChromaDB   │
                   ◄──────────────────────────────────│             │
                        (Embed, Index)                 │  Vectors    │
                                                       │  Metadata   │
                                                       └─────────────┘

                              QUERY PHASE
    ┌─────────────┐                                    ┌─────────────┐
    │             │     neuralmind query               │             │
    │   User      │ ─────────────────────────────────► │  NeuralMind │
    │   Query     │     "How does auth work?"          │             │
    └─────────────┘                                    └──────┬──────┘
                                                              │
                          ┌───────────────────────────────────┼───────────────────────────────────┐
                          │                                   │                                   │
                          ▼                                   ▼                                   ▼
                   ┌─────────────┐                     ┌─────────────┐                     ┌─────────────┐
                   │             │                     │             │                     │             │
                   │  L0 + L1    │                     │     L2      │                     │     L3      │
                   │  Identity   │                     │  Community  │                     │   Vector    │
                   │  Summary    │                     │  Expansion  │                     │   Search    │
                   │             │                     │             │                     │             │
                   └──────┬──────┘                     └──────┬──────┘                     └──────┬──────┘
                          │                                   │                                   │
                          └───────────────────────────────────┼───────────────────────────────────┘
                                                              │
                                                              ▼
                                                       ┌─────────────┐
                                                       │             │
                                                       │  Context    │
                                                       │  Selector   │
                                                       │             │
                                                       │  Merge      │
                                                       │  Dedupe     │
                                                       │  Format     │
                                                       └──────┬──────┘
                                                              │
                                                              ▼
                                                       ┌─────────────┐
                                                       │             │
                                                       │  Optimized  │
                                                       │  Context    │
                                                       │             │
                                                       │  ~1000 tok  │
                                                       └─────────────┘
```

---

## Component Architecture

```
┌──────────────────────────────────────────────────────────────────────────┐
│                        COMPONENT DIAGRAM                                  │
└──────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────┐
│                            NeuralMind                                    │
│                          (core.py)                                       │
│                                                                          │
│  ┌─────────────────────────────────────────────────────────────────┐    │
│  │  Public API                                                      │    │
│  │                                                                  │    │
│  │  • build()      - Generate/update embeddings                     │    │
│  │  • wakeup()     - Get minimal context                            │    │
│  │  • query()      - Get query-optimized context                    │    │
│  │  • search()     - Direct semantic search                         │    │
│  │  • benchmark()  - Performance testing                            │    │
│  │  • get_stats()  - Index statistics                               │    │
│  └─────────────────────────────────────────────────────────────────┘    │
│                                    │                                     │
│                    ┌───────────────┴───────────────┐                     │
│                    │                               │                     │
│                    ▼                               ▼                     │
│  ┌─────────────────────────────┐   ┌─────────────────────────────┐      │
│  │      GraphEmbedder          │   │      ContextSelector        │      │
│  │      (embedder.py)          │   │   (context_selector.py)     │      │
│  │                             │   │                             │      │
│  │  • load_graph()             │   │  • get_l0_identity()        │      │
│  │  • embed_nodes()            │   │  • get_l1_summary()         │      │
│  │  • search()                 │   │  • get_l2_context()         │      │
│  │  • get_node()               │   │  • get_l3_search()          │      │
│  │                             │   │  • get_context()            │      │
│  └──────────────┬──────────────┘   └──────────────┬──────────────┘      │
│                 │                                  │                     │
│                 ▼                                  │                     │
│  ┌─────────────────────────────┐                   │                     │
│  │        ChromaDB             │◄──────────────────┘                     │
│  │    (Vector Database)        │                                         │
│  │                             │                                         │
│  │  • Collections              │                                         │
│  │  • Embeddings               │                                         │
│  │  • Metadata                 │                                         │
│  │  • Similarity Search        │                                         │
│  └─────────────────────────────┘                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## Token Budget Management

### Budget Allocation

```
┌─────────────────────────────────────────────────────────────────┐
│                    TOKEN BUDGET ALLOCATION                       │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  WAKE-UP CONTEXT (Starting a conversation)                       │
│  ├── L0: Identity         100 tokens  ████                       │
│  └── L1: Summary          500 tokens  ████████████████████       │
│                           ─────────────                          │
│                           600 tokens total                       │
│                                                                  │
│  QUERY CONTEXT (Specific questions)                              │
│  ├── L0: Identity         100 tokens  ████                       │
│  ├── L1: Summary          500 tokens  ████████████████████       │
│  ├── L2: On-Demand        400 tokens  ████████████████           │
│  └── L3: Search           500 tokens  ████████████████████       │
│                           ─────────────                          │
│                           1500 tokens max                        │
│                                                                  │
│  COMPARISON                                                      │
│  ├── Full Codebase     50,000 tokens  ████████████████████████   │
│  ├── NeuralMind Query   1,000 tokens  ██                         │
│  └── Reduction              50x                                  │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### Dynamic Budget Adjustment

L2 and L3 budgets are dynamic based on:

1. **Query Complexity**: Simple queries may need less L2/L3
2. **Result Quality**: High-confidence matches get more tokens
3. **Community Size**: Larger communities may need more context
4. **Deduplication**: Overlapping results reduce effective usage

```python
# Budget allocation logic (simplified)
def allocate_budget(query_complexity: float) -> TokenBudget:
    base_l2 = 200
    base_l3 = 200
    
    # Scale based on complexity (0.0 - 1.0)
    l2_budget = base_l2 + int(300 * query_complexity)
    l3_budget = base_l3 + int(300 * query_complexity)
    
    return TokenBudget(
        l0=100,
        l1=500,
        l2=min(l2_budget, 500),
        l3=min(l3_budget, 500),
        total=100 + 500 + l2_budget + l3_budget
    )
```

---

## Embedding Strategy

### Embedding Model

NeuralMind uses ChromaDB's default embedding function, which typically uses:
- **Model**: `all-MiniLM-L6-v2` (or similar)
- **Dimensions**: 384
- **Type**: Sentence transformers

### What Gets Embedded

```
┌─────────────────────────────────────────────────────────────────┐
│                    EMBEDDING TARGETS                             │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  For each node in graph.json:                                    │
│                                                                  │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │  Embedding Text = Concatenation of:                      │    │
│  │                                                          │    │
│  │  1. Node name          "authenticate_user"               │    │
│  │  2. Node type          "function"                        │    │
│  │  3. Description        "Validates user credentials..."   │    │
│  │  4. File path          "users/auth/handlers.py"          │    │
│  │  5. Docstring          "Args: credentials (dict)..."     │    │
│  │                                                          │    │
│  └─────────────────────────────────────────────────────────┘    │
│                                                                  │
│  Metadata stored:                                                │
│  • node_id                                                       │
│  • node_type                                                     │
│  • community_id                                                  │
│  • file_path                                                     │
│  • content_hash (for incremental updates)                        │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### Incremental Updates

```python
# Incremental embedding logic
def should_embed(node: dict, existing_hash: str) -> bool:
    current_hash = hash_node_content(node)
    return current_hash != existing_hash

# Only embed changed nodes
for node in graph['nodes']:
    if should_embed(node, get_stored_hash(node['id'])):
        embed_and_store(node)
    else:
        skip_count += 1
```

---

## Community Detection

NeuralMind leverages community structure from the knowledge graph to understand logical code groupings.

### How Communities Work

```
┌─────────────────────────────────────────────────────────────────┐
│                    COMMUNITY STRUCTURE                           │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Community: A cluster of closely related code entities           │
│                                                                  │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐  │
│  │ Community 1     │  │ Community 2     │  │ Community 3     │  │
│  │ (Authentication)│  │ (Task Engine)   │  │ (API Layer)     │  │
│  │                 │  │                 │  │                 │  │
│  │ • login()       │  │ • create_task() │  │ • /api/tasks    │  │
│  │ • logout()      │  │ • update_task() │  │ • /api/users    │  │
│  │ • verify_jwt()  │  │ • delete_task() │  │ • middleware    │  │
│  │ • User model    │  │ • Task model    │  │ • validators    │  │
│  └────────┬────────┘  └────────┬────────┘  └────────┬────────┘  │
│           │                    │                    │            │
│           └────────────────────┼────────────────────┘            │
│                                │                                 │
│                    Cross-community relationships                 │
│                    (imports, calls, dependencies)                │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### Community Expansion Strategy

When a query matches entities in a community, NeuralMind can expand to load related context:

```python
def expand_context(matched_nodes: List[Node], budget: int) -> List[Node]:
    # Get communities of matched nodes
    communities = set(n.community for n in matched_nodes)
    
    expanded = list(matched_nodes)
    remaining_budget = budget - sum(estimate_tokens(n) for n in matched_nodes)
    
    # Add other nodes from same communities
    for community_id in communities:
        community_nodes = get_community_nodes(community_id)
        for node in community_nodes:
            if node not in expanded:
                node_tokens = estimate_tokens(node)
                if node_tokens <= remaining_budget:
                    expanded.append(node)
                    remaining_budget -= node_tokens
    
    return expanded
```

---

## Performance Optimization

### Build Performance

| Optimization | Description | Impact |
|-------------|-------------|--------|
| Incremental Updates | Only embed changed nodes | 10-100x faster rebuilds |
| Content Hashing | SHA-256 hash of node content | Accurate change detection |
| Batch Embedding | Process nodes in batches | Reduced API overhead |
| Parallel Processing | Multi-threaded for large graphs | 2-4x faster initial build |

### Query Performance

| Optimization | Description | Impact |
|-------------|-------------|--------|
| Vector Indexing | ChromaDB HNSW index | Sub-linear search time |
| Layer Caching | Cache L0/L1 per session | Instant wake-up |
| Result Caching | Cache recent query results | Instant repeat queries |
| Early Termination | Stop search at confidence threshold | Faster for clear queries |

### Memory Optimization

```
┌─────────────────────────────────────────────────────────────────┐
│                    MEMORY USAGE                                  │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Component              Typical Size                             │
│  ─────────────────────────────────────                           │
│  ChromaDB Index         10-50 MB (depends on codebase size)      │
│  Loaded Graph           5-20 MB                                  │
│  Embedding Model        ~100 MB (shared across instances)        │
│  Query Cache            1-5 MB                                   │
│                                                                  │
│  Total per project:     ~20-80 MB                                │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

---

## Synapse Layer (v0.4)

In v0.4.0 NeuralMind grew a **second brain that runs alongside the LLM**.
The 4-layer progressive disclosure system above is unchanged — that's the
retrieval brain. The synapse layer adds an *associative* brain that learns
from how the agent and the codebase actually interact, so retrieval gets
sharper the longer the system runs.

### Two-brain split

| Role | Substrate | State | What it's good at |
|------|-----------|-------|-------------------|
| Claude / agent (cortex) | Transformer | Stateless context window | Reasoning, generation |
| NeuralMind retrieval (4 layers) | Vector DB + graph | Static, rebuilt on `build` | Query-aware compression |
| **NeuralMind synapses (v0.4)** | **SQLite weighted graph** | **Persistent, continuously learning** | **Usage-based associative recall** |

The agent never sees the synapse weights directly. It just gets better
context: spreading-activation neighbors injected via the
`UserPromptSubmit` hook, plus a markdown export that lands in Claude
Code's auto-memory directory each session.

### Synapse store

`neuralmind/synapses.py` — SQLite at `<project>/.neuralmind/synapses.db`.
Stdlib only.

- **Edges** are undirected, keyed by canonical `(node_a, node_b)` ordering.
- **Reinforce** is Hebbian: every pairwise edge among co-activated nodes
  gets a learning-rate bump, capped at 1.0.
- **Decay** is multiplicative; weights below the prune threshold are deleted.
- **Long-term potentiation (LTP):** edges crossing an activation count
  threshold get a weight floor and slower decay, so frequently-used
  associations don't get forgotten.
- **Spreading activation** propagates a query's seed energy outward
  through weighted edges. Hub-degree normalization scales contributions
  from over-connected nodes so a single utility file can't dominate.

### Activation channels

Five paths feed the synapse store, all funnelling through `activate()`:

```
                      ┌────────────────────────┐
                      │  SynapseStore (SQLite) │
                      │  • reinforce()         │
                      │  • decay()             │
                      │  • spread()            │
                      └──────────▲─────────────┘
                                 │ activate()
       ┌─────────────────────────┼─────────────────────────┐
       │                         │                         │
┌──────┴──────┐         ┌────────┴────────┐       ┌────────┴────────┐
│ query()     │         │ FileActivity    │       │ Claude Code     │
│ — Hebbian   │         │   Watcher       │       │   hooks         │
│ on top      │         │ — co-edited     │       │ — SessionStart, │
│ search hits │         │   files wire    │       │   UserPromptSub.│
│             │         │   together      │       │   PreCompact    │
└─────────────┘         └─────────────────┘       └─────────────────┘
```

### File watcher

`FileActivityWatcher` (debounced, watchdog or polling) groups edits
within a window into a single co-activation batch. `core.activate_files()`
resolves each path to its graph node ids via the embedder and feeds the
batch to `reinforce()`. Started by the `neuralmind watch` CLI.

### Memory export

`neuralmind/synapse_memory.py` renders the learned graph as markdown:
strongest pairs (LTP-tagged), top hubs, summary stats. Writes to two
locations:

- `<project>/.neuralmind/SYNAPSE_MEMORY.md` (always)
- `~/.claude/projects/<slug>/memory/synapse-activations.md` (when Claude Code's auto-memory directory exists)

Add `@.neuralmind/SYNAPSE_MEMORY.md` to `CLAUDE.md` so the file gets
imported into every session even when the auto-memory path doesn't apply.

### Why this isn't the same as the v0.3.2 reranker

- The **reranker** boosts vector-search results based on patterns found
  in past queries. Static index, batch analysis, post-hoc re-ranking.
- The **synapse layer** is a continuously updated weighted graph that
  contributes its own retrieval path (spreading activation), independent
  of vector search. Updates happen on every query, every tool call,
  every file edit.

The two are complementary: reranker re-orders the L3 hits the synapse
layer also sees as activation seeds.

---

## See Also

- [API Reference](API-Reference.md) - Python API documentation
- [CLI Reference](CLI-Reference.md) - Command-line interface
- [Integration Guide](Integration-Guide.md) - MCP and tool integrations
- [Release Notes v0.4.0](../blob/main/RELEASE_NOTES_v0.4.0.md) - Synapse layer launch notes
