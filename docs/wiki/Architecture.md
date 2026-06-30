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
- Top semantic + keyword matches
- Code snippets with context
- Entity descriptions
- File paths and locations

**Search Strategy** *(v0.38.0 hybrid)*:
1. Embed query using same model as index → vector results
2. BM25 keyword search (code-aware tokenisation) → keyword results
3. Merge both lists via Reciprocal Rank Fusion (RRF, k=60)
4. Filter duplicates from L2
5. Format top N results

Set `NEURALMIND_BM25=0` to revert to pure vector search.

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

NeuralMind embeds **100% locally** — there is **no cloud embedding API call**, on
any backend ([`SECURITY.md`](https://github.com/dfrostar/neuralmind/blob/main/SECURITY.md)).
The model is **pinned**, not "default / or similar":

- **Model**: `all-MiniLM-L6-v2` — `_MODEL_NAME` in
  [`neuralmind/onnx_embedder.py`](https://github.com/dfrostar/neuralmind/blob/main/neuralmind/onnx_embedder.py)
- **Dimensions**: 384 (`OnnxMiniLMEmbedder.dim`)
- **Max tokens / batch**: 256 / 32
- **Runtime**: `onnxruntime` (CPU), tokenized with `tokenizers` — the bundled
  ChromaDB-free path (default on Linux / Apple Silicon / Windows x64 since v0.29.0)
- **Model fetch**: one-time download of a **SHA256-pinned** archive
  (`_ARCHIVE_SHA256`) into `~/.cache/neuralmind/onnx_models/`; a corrupted or swapped
  download **fails loudly**. Pre-stage it for air-gapped installs via
  `NEURALMIND_ONNX_MODEL_DIR` — no network at build, query, or runtime thereafter.
- **Backend parity**: the ONNX embedder produces vectors **byte-identical** to
  ChromaDB's `all-MiniLM-L6-v2` (verified cosine 1.0, max elementwise diff 0.0), so
  the `turbovec` (TurboQuant, 8–16× smaller index) and `chroma` backends retrieve
  equivalently — only the index representation differs.

**Can I swap the model?** Not as a supported knob today, and deliberately so: the
embedder is the same one ChromaDB pins, and the community-detection ids and synapse
edge keys are computed against *these* vectors. Swapping the encoder would
invalidate a warm synapse store and the parity guarantee above. If you need a
different encoder, that's a code change to `onnx_embedder.py` / the backend, not a
config flag — and you'd rebuild the index and re-warm memory from scratch.

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

### Why this isn't the same as the v0.3.2 reranker (removed in v0.25.0)

NeuralMind once had a second learning mechanism, the `learned_patterns`
cooccurrence **reranker** (v0.3.2). **It was removed in v0.25.0** after a
2×2 A/B on the benchmark fixture showed it added 0.0 points to top-k hit
rate whether the synapse layer was on or off (71.7% → 71.7% cold, 83.3% →
83.3% warm), while the synapse layer alone added +11.6 points. The
reranker was also runtime-inert on the warm path — the synapse boost
re-sort discarded its ordering anyway. The architectural reason the two
were never equivalent:

- The **reranker** boosted vector-search results based on patterns found
  in past queries. Static index, batch analysis triggered by a manual
  `neuralmind learn` step, post-hoc re-ranking, no forgetting.
- The **synapse layer** is a continuously updated weighted graph that
  contributes its own retrieval path (spreading activation), independent
  of vector search. Updates happen on every query, every tool call, and
  every file edit, and unused edges decay so recall tracks current usage.

The reranker only ever re-ordered the L3 hits the synapse layer already
sees as activation seeds, so its ordering was both redundant and
discarded. The synapse layer is now the single learning system. See the
[v0.25.0 release notes](https://github.com/dfrostar/neuralmind/blob/main/RELEASE_NOTES_v0.25.0.md)
for the full evidence.

---

## Event Bus and JSONL Bridge (v0.6)

v0.6.0 added a third structural piece: an **event bus** that turns
"the brain is learning" from a claim into a visible, real-time
signal. The bus and its cross-process counterpart (the JSONL
bridge) are how `neuralmind serve` knows when to pulse a node on
the canvas.

### Why an event bus

Pre-v0.6.0, the synapse store reinforced on every co-activation but
the experience was invisible. You had to refresh the graph view to
see a state change. We wanted the canvas to feel like a heartbeat
monitor — pulse the instant a node lights up — so we needed a
push-based notification path from the model layer to the UI.

We considered three options:

| Option | Verdict |
|---|---|
| Polling — UI re-reads `synapses.db` every N ms | Wasteful; introduces lag proportional to N |
| WebSocket | More than we need; adds a real dependency surface |
| **In-process event bus + SSE** | Stdlib-only, push-based, O(1) when nobody's listening |

We picked the third option. `event_bus.py` is a tiny pub/sub
singleton accessed via `get_event_bus()`. `SynapseStore.reinforce()`
publishes a `synapse` event after every pair-touching call;
`FileActivityWatcher` publishes a `file_activity` event after every
coalesced batch. `serve`'s `/api/events` endpoint subscribes and
forwards to the browser as a long-lived Server-Sent Events stream.

### Two-brain diagram, refreshed

```
                       ┌──────────────────────────────┐
                       │  Browser canvas              │
                       │  • pulse rings               │
                       │  • sidebar event log         │
                       └─────────────▲────────────────┘
                                     │ SSE: /api/events
                       ┌─────────────┴────────────────┐
                       │  EventBus (event_bus.py)     │
                       │  • publish() is O(1) when    │
                       │    no subscribers + no       │
                       │    JSONL writer configured   │
                       └─────▲──────────────────▲─────┘
                             │                  │ tail
        ┌────────────────────┼─────┐  ┌─────────┴───────────┐
        │                          │  │ events.jsonl bridge │
┌───────┴─────────┐  ┌─────────────┴┐ │ (event_log.py)      │
│ SynapseStore    │  │ FileActivity │ │ ─ writer: appends   │
│ .reinforce()    │  │ Watcher      │ │   on publish        │
│ publishes       │  │ publishes    │ │ ─ tailer: re-emits  │
│ "synapse" event │  │ "file_       │ │   foreign events    │
└─────────────────┘  │  activity"   │ └─────────────────────┘
                     │  events      │
                     └──────────────┘
```

### Why the JSONL bridge

The in-process bus is great when `serve` and the activity source
share a Python process. The common real-world case is *not* that:
you run `neuralmind serve` in one terminal, `neuralmind watch` in
another, and a Claude Code session in a third — three processes,
three sources of brain activity, one canvas you'd like to show all
of them.

`event_log.py` is the deliberately boring side channel that makes
this work:

- Every `event_bus.publish()` call appends one JSON line to
  `<project>/.neuralmind/events.jsonl`.
- The `serve` process tails that file in a background thread, drops
  events it originated itself (deduped by event id), and republishes
  the rest into its local bus.
- `NEURALMIND_EVENT_LOG=0` disables the writer for opt-out. The
  in-process bus is unaffected.

The design choice worth stating: the JSONL is a **fallback, not a
queue**. The bus is the primary path; the file is best-effort and
reconstructs itself if it disappears or rolls. We deliberately did
not build a real IPC mechanism — sockets, gRPC, named pipes —
because the cost/benefit didn't justify it. JSONL is observable
with `tail -f` and survives process restarts. Good enough.

### What this unlocks: the multi-agent shared brain

Pre-v0.6.0, every agent talking to a project reinforced the same
`synapses.db` but you couldn't see it. The synapse store was
shared; the *experience* wasn't. Three tools talking to a black
box.

In v0.6.0, the JSONL bridge makes the union visible. Claude Code,
Cursor, OpenClaw, and Hermes-Agent all publish to
`events.jsonl`; `neuralmind serve` aggregates them into one canvas.
Every tool call from any agent pulses the corresponding nodes. The
brain isn't just learning your codebase; it's learning across every
tool you use, and you can finally see the union.

See [`docs/use-cases/multi-agent.md`](../../docs/use-cases/multi-agent.md)
for the day-by-day walkthrough.

### Files

- [`neuralmind/event_bus.py`](../../neuralmind/event_bus.py) —
  pub/sub singleton, `get_event_bus()` accessor, `Event` dataclass.
  No external deps.
- [`neuralmind/event_log.py`](../../neuralmind/event_log.py) —
  JSONL writer + tailer for the cross-process bridge. No external
  deps.
- `tests/test_event_bus.py`, `tests/test_event_log.py` — stdlib-only
  tests; they lock in that `reinforce()` and the watcher publish
  the right events, and that the tailer dedupes correctly.

### Performance footprint

- `event_bus.publish()` is O(1) when there are **no** subscribers
  AND **no** writer configured — emit-points cost nothing on
  headless servers or CLI-only runs.
- With the writer enabled, each publish is one `fcntl`-locked
  `write()` on the JSONL file. Measured overhead on a 2026 dev
  laptop: ~50 µs/event.
- The tailer is one background thread per `serve` process.

---

## Hybrid Search (v0.38.0)

Pure vector search excels at semantic similarity ("how does authentication
work?") but underperforms on exact identifiers ("UserService", "get_auth_token").
v0.38.0 adds a BM25 sparse keyword index that runs alongside the vector search
and whose results are merged at query time via **Reciprocal Rank Fusion**.

### BM25 index

- **Code-aware tokenisation**: camelCase (`UserService` → `["user","service"]`),
  snake_case, dots, digits handled; short/digit-only tokens dropped.
- **Atire BM25 formulation** (k1=1.5, b=0.75): standard parameters with strong
  prior performance on short, structured text.
- **Persisted** to `<project>/.neuralmind/bm25_index.json` at end of
  `neuralmind build` — survives daemon restarts.
- **Kill switch**: `NEURALMIND_BM25=0` disables the merge; the vector path is
  unaffected.

### Reciprocal Rank Fusion merge

```
score(d) = Σ_list  1 / (k + rank(d, list))    k = 60
```

The merged list is re-normalised to [0, 1]. Results present in both lists get an
`_hybrid_kw_rank` annotation in the trace output for debugging.

### Explicit feedback loop (v0.38.0)

The `neuralmind_feedback` MCP tool closes the learning loop:

| Signal | Effect |
|---|---|
| `positive` + `context_node_ids` | `SynapseStore.reinforce([node_id] + context_node_ids)` — strengthens associations |
| `negative` | `SynapseStore.decay_node(node_id)` — weakens edges without deleting LTP-protected ones |

Agents call this tool after using a retrieval result. Over time, nodes the agent
finds useful accumulate stronger synapse weights; nodes that produce bad results
have their edges softened so they surface less.

---

## Index format & debugging (power-user reference)

You don't have to treat the index as a black box. Everything below is on-disk and
inspectable, and there's a command for "why did my query miss?"

### What's on disk

| Artifact | Path | Format | Inspect with |
|---|---|---|---|
| **Code graph** | `graphify-out/graph.json` | plain JSON (nodes + edges + rationale) | any JSON tool; `embedder.get_file_nodes()` / `get_file_edges()` |
| **Vector index** | `graphify-out/neuralmind_db/` | ChromaDB `PersistentClient` (SQLite) **or** turbovec (TurboQuant) | `neuralmind stats`; backend-specific |
| **Synapse store** | `.neuralmind/synapses.db` | SQLite (edge weights + directional transitions + namespaces + tuner meta) | `neuralmind memory inspect`; `sqlite3` |
| **Memory export** | `.neuralmind/SYNAPSE_MEMORY.md` | Markdown (auto-loaded by Claude Code) | read it directly |
| **Event log** | `.neuralmind/events.jsonl` | JSONL activity stream | `neuralmind savings`; the graph view |

The IR is **schema-versioned** and round-trips losslessly — `neuralmind validate`
checks the contract **without a vector backend**, so you can verify graph integrity
in CI before embedding.

### "Why did this query return *that*?"

The retrieval path is transparent and reproducible (same query + same index ⇒ same
context). The inspection surface, from cheapest to deepest:

| Command | Answers |
|---|---|
| `neuralmind stats` | node count, community distribution, resolved backend, db path |
| `neuralmind doctor` | is every subsystem healthy (graph, index, synapses, MCP, hooks)? + exact fix commands |
| `neuralmind validate` | does the graph satisfy the versioned IR contract? (no backend needed) |
| `neuralmind query … --trace` | per-layer candidates, cluster scoring with **vector-vs-synapse attribution**, final hits |
| `neuralmind query … --explain` | human-readable "why this context" — L0–L3 token budget, communities loaded, top search hits, synapses that fired (implies `--trace`) |
| `neuralmind query … --relevance` | machine-readable per-file/per-node `relevance` sidecar: vector **score**, synapse **boost**, **recall flag**, **line spans** (also `neuralmind_query(include_relevance=true)`) |
| `neuralmind probe` | label-free self-test — queries each symbol by its *rationale* (not its name) and reports retrieval blind spots (~0.79 MRR with real gaps disclosed) |
| `neuralmind savings` | cumulative token savings vs estimated full-codebase cost, per query, from the event log |
| `neuralmind review` | spreading-activation co-break candidates for the current `git diff` (also `neuralmind_review` MCP tool) |
| `neuralmind memory inspect` | synapse contribution by namespace (`branch:` / `personal` / `shared` / `ephemeral`); `memory export` dumps a versioned JSON bundle |

If `--trace` shows the gold file *did* embed but ranked low, the usual causes are:
a weak/missing docstring (the rationale layer carries semantic signal — see
[Embedding Strategy](#embedding-strategy)), a cold synapse store (recall warms with
use — [Learning Guide](Learning-Guide)), or a question that needs more breadth than
one budget holds (see [Limits & Failure Modes](Limits-and-Failure-Modes)).

---

## See Also

- [Limits & Failure Modes](Limits-and-Failure-Modes.md) - Where it stops working, and what to do then
- [Benchmarks & Results](Benchmarks.md) - Every measured, CI-gated number + reproduction commands
- [API Reference](API-Reference.md) - Python API documentation
- [CLI Reference](CLI-Reference.md) - Command-line interface
- [Integration Guide](Integration-Guide.md) - MCP and tool integrations
- [Release Notes v0.4.0](https://github.com/dfrostar/neuralmind/blob/main/RELEASE_NOTES_v0.4.0.md) - Synapse layer launch notes
- [Release Notes v0.38.0](https://github.com/dfrostar/neuralmind/blob/main/RELEASE_NOTES_v0.38.0.md) - Hybrid search + feedback loop
