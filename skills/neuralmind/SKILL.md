---
name: neuralmind
description: Answer questions about a code repository in ~800 tokens instead of loading 50,000+ tokens of raw source. Use whenever the user asks how something works, where something is defined, who calls what, or to explore an unfamiliar file. Provides progressive context disclosure (L0 identity → L1 architecture → L2 relevant clusters → L3 semantic search) and a learned synapse graph for usage-based recall.
version: 0.5.2
author: dfrostar
license: MIT
tags:
  - code-intelligence
  - retrieval
  - context-compression
  - mcp
triggers:
  - how does
  - where is
  - find function
  - find class
  - explain module
  - explain this file
  - trace callers
  - who calls
  - what calls
  - architecture overview
  - codebase question
  - unfamiliar repo
  - onboard to repo
allowed_tools:
  - neuralmind_wakeup
  - neuralmind_query
  - neuralmind_search
  - neuralmind_skeleton
  - neuralmind_synaptic_neighbors
  - neuralmind_synapse_stats
  - neuralmind_synapse_decay
  - neuralmind_export_synapse_memory
  - neuralmind_build
  - neuralmind_stats
  - neuralmind_benchmark
runtime:
  binaries:
    - neuralmind
    - neuralmind-mcp
  install: pip install neuralmind
metadata:
  complexity: low
  category: developer-tools
---

# NeuralMind

You have access to a neural index of the current project. Prefer it over
reading source files directly whenever you need to **locate**, **explain**,
or **navigate** code. The index returns compact, structured context that is
typically 40–70× cheaper than raw source.

The index is **not** a code rewriter or executor. It retrieves; you reason.
Treat it like a librarian: ask narrow questions, escalate only on a miss.

## Prerequisite check

Before the first call in a session, confirm the index exists:

```
neuralmind_stats(project_path=".")
```

If `built: false`, the project hasn't been indexed yet. Tell the user to run:

```
graphify update . && neuralmind build .
```

…and stop. Do not fabricate answers when the index is missing.

## Decision tree — which tool to call

```
New session / first question about this repo?
  └─► neuralmind_wakeup            ~400–600 tokens (L0 + L1)

Specific code question?
  └─► neuralmind_query             ~800–1,100 tokens (L0+L1+L2+L3)
      The single most-used tool. Hand it the user's question verbatim.

About to open a file you don't know?
  └─► neuralmind_skeleton          5–15× cheaper than reading the file
      Returns functions, call graph, cross-file edges. Only fall back to
      raw Read when you need an implementation body.

Looking for a specific symbol (function, class, file)?
  └─► neuralmind_search            ranked semantic matches

Want associations the agent has learned over time?
  └─► neuralmind_synaptic_neighbors   spreading activation over the
                                      synapse graph; complements semantic
                                      search with usage-based recall

Made code changes in this session?
  └─► neuralmind_build              incremental re-embedding
```

## Output shape (so you know what to expect)

`wakeup` / `query` returns sections like:

```
## Project: <name>
<one-paragraph description>
Knowledge Graph: N entities, M clusters

## Architecture Overview
### Code Clusters
- Cluster 5 (45 entities): function — authenticate_user, hash_password, …
- Cluster 12 (23 entities): class — UserController, AuthMiddleware, …

## Relevant Code Areas      ← query only
### Cluster 5 (relevance: 1.73)
- authenticate_user (code) — auth.py
- verify_token (code) — auth.py

## Search Results            ← query only
- AuthMiddleware (score: 0.91) — middleware.py
- jwt_handler   (score: 0.85) — auth/jwt.py

Tokens: 847 | 59.0x reduction | Layers: L0, L1, L2, L3
```

`skeleton` returns functions with line numbers, an intra-file call graph,
and cross-file edges — without the implementation bodies. When you need a
body, follow up with a normal file read.

## Synapse layer (learned associations)

NeuralMind keeps a persistent weighted graph of code nodes and strengthens
edges between nodes that get co-activated within the same task. This means:

- The longer the project is used, the better `neuralmind_synaptic_neighbors`
  becomes at surfacing related-but-not-semantically-similar code.
- If the project has a `.neuralmind/SYNAPSE_MEMORY.md`, treat it as
  authoritative context about which code areas tend to move together.
- The graph decays over time so stale associations fade. Do not panic if a
  past co-activation no longer shows up.

You do not need to manage the synapse graph manually. The exposed tools
(`neuralmind_synapse_stats`, `neuralmind_synapse_decay`,
`neuralmind_export_synapse_memory`) are for diagnostic / housekeeping use,
not for routine question-answering.

## Anti-patterns

- **Don't** call `neuralmind_query` with a one-word search term — use
  `neuralmind_search` for that. `query` expects a natural-language question.
- **Don't** call `neuralmind_build` defensively on every turn. It's only
  needed after code changes within the session, or when `stats` shows the
  index is stale.
- **Don't** loop over `neuralmind_skeleton` for every file in a directory.
  Ask one good `neuralmind_query` instead — the L2 layer surfaces the right
  files for you.
- **Don't** suppress retrieval with `NEURALMIND_BYPASS=1` unless the user
  has explicitly asked for raw source. The bypass is a debugging hatch.

## Failure modes

- **Tool unavailable / connection closed:** the MCP server isn't wired up
  for this client. Fall back to `neuralmind` CLI (`neuralmind wakeup .`,
  `neuralmind query . "…"`) via the shell. Same outputs, same semantics.
- **Empty results from `query`:** the question may be too broad or the
  repo wasn't indexed at sufficient depth. Try `neuralmind_search` with the
  most distinctive term from the question.
- **`built: false`:** stop and tell the user. See *Prerequisite check*.

## Environment toggles (for reference)

These are set by the user, not by you. They change retrieval behavior:

- `NEURALMIND_BYPASS=1` — skip compression; return raw source.
- `NEURALMIND_SYNAPSE_INJECT=0` — disable prompt-time synapse recall.
- `NEURALMIND_SYNAPSE_EXPORT=0` — disable markdown export of learned
  associations.

## One-line summary

Ask NeuralMind first. Read source only when you need the body.
