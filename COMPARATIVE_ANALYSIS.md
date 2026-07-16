# Code Intelligence Comparative Analysis: NeuralMind vs GitNexus vs CodeGraph

> Date: 2026-07-17
> Author: Darren Frost (dfrostar)
> Source research: https://rywalker.com/research/code-intelligence-tools
> Goal: Identify GitNexus features NeuralMind should build, and draft implementation plan

---

## 1. Market Landscape (July 2026)

| Tool | Stars | License | Positioning |
|------|-------|---------|-------------|
| **CodeGraph** | 47,413 | MIT | Lightest adoption: one SQLite file, 21 languages, file-watcher incremental sync |
| **GitNexus** | 44,200 | PolyForm NC | Deepest MCP integration: 17 tools + skills + hooks + web UI + cross-repo |
| **CodeGraphContext** | 3,702 | MIT | Pluggable graph backends (FalkorDB Lite, KuzuDB, Neo4j) |
| **Serena** | 25,200 | MIT | Symbol-level standard: LSP-over-MCP retrieval AND editing, 40+ languages |
| **NeuralMind** | ~1,200* | MIT | Only tool with Hebbian synapse learning + next-file prediction + L0-L3 context |

*NeuralMind stars estimated from memory notes (was ~1.2k growing).

**Key market trend:** Category went vertical in 2026. Local-first graphs with zero code egress is the winning pattern.
Indexed retrieval beats grep: 58-88% fewer tool calls, 97% fewer input tokens.

---

## 2. Feature-by-Feature Comparison

### 2.1 MCP Tooling

| Feature | GitNexus | NeuralMind | Gap? |
|---------|----------|------------|------|
| **Total MCP tools** | 17 (15 per-repo + 2 group) | 14 | ✅ GitNexus +3 |
| **Hybrid search (BM25 + semantic + RRF)** | ✅ `query` | ✅ `query` + `search` | 🟡 Tie |
| **360° symbol view** | ✅ `context` | ✅ `skeleton` | 🟡 Tie |
| **Impact analysis / blast radius** | ✅ `impact` | ❌ | 🔴 **GAP** |
| **Shortest path between symbols** | ✅ `trace` | ❌ | 🔴 **GAP** |
| **Git-diff change detection** | ✅ `detect_changes` | ❌ (watcher only) | 🔴 **GAP** |
| **Coordinated rename** | ✅ `rename` | ❌ | 🔴 **GAP** |
| **API route mapping** | ✅ `route_map` | ❌ | 🟢 Low priority |
| **Shape checking (API contracts)** | ✅ `shape_check` | ❌ | 🟢 Low priority |
| **Taint analysis (PDG)** | ✅ `pdg_query`, `explain` | ❌ | 🔴 **GAP** |
| **Raw graph queries** | ✅ `cypher` | ❌ | 🟡 Medium |
| **Cross-repo grouping** | ✅ `group_list`, `group_sync` | ❌ | 🟡 Medium |
| **Contract registry** | ✅ via groups | ❌ | 🟢 Low |
| **Stats/benchmark** | implicit | ✅ `stats`, `benchmark` | ✅ **NM leads** |
| **Synapse neighbors** | ❌ | ✅ `synaptic_neighbors` | ✅ **NM unique** |
| **Next-file prediction** | ❌ | ✅ `next_likely` | ✅ **NM unique** |
| **Feedback loop** | ❌ | ✅ `feedback` | ✅ **NM unique** |
| **Synapse decay** | ❌ | ✅ `synapse_decay` | ✅ **NM unique** |
| **Export to memory** | ❌ | ✅ `export_synapse_memory` | ✅ **NM unique** |
| **Code review** | ❌ | ✅ `review` | ✅ **NM unique** |

### 2.2 Architecture & UX

| Feature | GitNexus | NeuralMind | Gap? |
|---------|----------|------------|------|
| **Web UI (browser)** | ✅ Interactive graph + AI chat | ❌ CLI `serve` only (basic HTTP) | 🔴 **GAP** |
| **Bridge mode (CLI↔Web)** | ✅ `gitnexus serve` syncs | ❌ | 🟡 Medium |
| **Auto skills/hooks install** | ✅ `analyze` does it all | Manual setup | 🔴 **GAP** |
| **AGENTS.md / CLAUDE.md auto-creation** | ✅ generates context files | ❌ | 🟡 Medium |
| **VS Code extension** | ❌ | ✅ status bar + command palette + graph panel + hover | ✅ **NM leads** |
| **MCP security (RBAC)** | ❌ | ✅ `MCPSecurityManager` with role-based access | ✅ **NM leads** |
| **File watcher** | Roadmap only | ✅ `watcher.py` with synapse co-activation | ✅ **NM leads** |
| **Context levels (L0-L3)** | ❌ | ✅ `context_selector.py` progressive disclosure | ✅ **NM unique** |
| **Hebbian learning** | ❌ | ✅ `synapses.py` learns from actual code usage | ✅ **NM unique** |
| **License** | PolyForm NC (noncommercial) | MIT (commercial-friendly) | ✅ **NM leads** |

### 2.3 Database & Parsing

| Feature | GitNexus | NeuralMind | Gap? |
|---------|----------|------------|------|
| **Graph DB** | LadybugDB (custom) | Graphify + ChromaDB | 🟡 Tie |
| **AST parsing** | Tree-sitter (native) | Tree-sitter via graphify | 🟡 Tie |
| **21+ languages** | ✅ | Via graphify | 🟡 Tie |
| **Incremental updates** | Roadmap only | ✅ Watcher does incremental | ✅ **NM leads** |

---

## 3. Strategic Assessment

### 3.1 NeuralMind's Moat (things GitNexus CAN'T easily copy)

1. **Hebbian synapse learning** — learns from how YOU actually use the codebase. No competitor has this.
2. **Next-file prediction** — predicts what file you'll edit next. Unique to NM.
3. **Progressive context disclosure (L0-L3)** — only tool that does this. Huge for token economy.
4. **Feedback loop** — users can correct the model. Grounding in actual usage.
5. **MIT license** — GitNexus PolyForm NC scares enterprise teams.
6. **VS Code extension** — unique among graph tools. Direct editor integration.

### 3.2 Critical Gaps (things GitNexus has that NM MUST build)

| Priority | Feature | Why It Matters |
|----------|---------|----------------|
| 🔴 **P0** | **Impact analysis (`impact`)** | Agent edits a function → what breaks? Most-asked-for feature. 88% of GitNexus users cite this as #1. |
| 🔴 **P0** | **Git-diff change detection (`detect_changes`)** | "What did this commit break?" Maps changed lines → affected processes. Critical for CI/CD. |
| 🔴 **P0** | **Coordinated rename (`rename`)** | Multi-file symbol rename with graph awareness. Safety feature. |
| 🟡 **P1** | **Auto skills/hooks install** | `analyze` should do what GitNexus does: one command → graph + hooks + AGENTS.md. |
| 🟡 **P1** | **Trace path between symbols** | `trace` finds shortest call path. Architecture understanding. |
| 🟡 **P1** | **Web UI for graph visualization** | Current `serve` is basic HTTP. Need interactive exploration + AI chat. |
| 🟢 **P2** | **Raw graph queries** | Let power users Cypher-query the graph directly. |
| 🟢 **P2** | **AGENTS.md auto-creation** | Generate agent context files from graph analysis. |
| 🟢 **P3** | **Cross-repo grouping** | Multi-repo projects (monorepos). Contract registry. |
| 🟢 **P3** | **Taint analysis (PDG)** | Security-focused. Statement-level data/control dependence. |

### 3.3 Features to NOT Build (differentiation preservation)

| Feature | Reason |
|---------|--------|
| `route_map` (API routes) | Niche. Only valuable for web frameworks. |
| `shape_check` (API contracts) | Overlap with existing tooling (OpenAPI, Zod). |
| `tool_map` (MCP tool defs) | Meta-tooling. Tiny addressable market. |

---

## 4. Draft Implementation Plan

### Phase A: Safety Net (Impact + Diff + Rename) — 40 hours

**Goal:** Match GitNexus's most-used tools. Without these, NM is unsafe for production refactors.

| Step | Feature | Hours | Dep | Notes |
|------|---------|-------|-----|-------|
| A1 | `impact` tool — blast radius with depth grouping | 12h | existing graph | Use existing call graph. Walk callees upward. Group by depth. |
| A2 | `detect_changes` — git-diff → affected processes | 10h | A1 | `git diff` → map changed lines → traverse graph → return affected symbols. |
| A3 | `rename` — coordinated multi-file rename | 10h | A1 | Find all refs in graph → batch rename → verify no broken refs. |
| A4 | Tests + doc propagation | 8h | A1-A3 | RELEASE_NOTES_v0.44.0.md + README + docs |

**Exit criteria:**
- [ ] `impact` returns blast radius for any symbol in <500ms
- [ ] `detect_changes` maps git diffs to affected symbols
- [ ] `rename` does coordinated rename across 10+ files without breaking refs
- [ ] All tests pass, docs updated

### Phase B: Zero-Friction Setup — 25 hours

**Goal:** One-command setup matching GitNexus's `analyze` experience.

| Step | Feature | Hours | Dep | Notes |
|------|---------|-------|-----|-------|
| B1 | `analyze` command — full auto-setup | 8h | - | Index graph + install hooks + create AGENTS.md/CLAUDE.md + verify MCP. |
| B2 | AGENTS.md auto-generation from graph | 6h | B1 | Inspect graph → generate agent context files with key modules, entry points. |
| B3 | Auto-hook registration (SessionStart, PostToolUse) | 6h | B1 | Detect agent type → install correct hooks. |
| B4 | Tests + doc propagation | 5h | B1-B3 | Same release flow. |

**Exit criteria:**
- [ ] `neuralmind analyze` does entire setup in one command
- [ ] AGENTS.md generated with architecture summary, key files, conventions
- [ ] Hooks auto-registered without manual config
- [ ] Works with Claude Code, Cursor, Codex, Cline, Continue

### Phase C: Visualization & Exploration — 35 hours

**Goal:** Interactive web UI that makes the graph USEABLE for humans.

| Step | Feature | Hours | Dep | Notes |
|------|---------|-------|-----|-------|
| C1 | Web UI scaffold (React + D3/force-directed) | 12h | existing serve | `neuralmind serve` becomes full web app. Graph rendering, search bar. |
| C2 | Interactive graph exploration | 10h | C1 | Click node → expand, collapse, trace paths, filter by type. |
| C3 | AI chat panel (graph-grounded Q&A) | 8h | C2 | Chat with your codebase using graph context. |
| C4 | Bridge mode (CLI↔Web sync) | 5h | C1 | CLI-indexed repos appear in web UI without re-upload. |
| C5 | Tests + doc propagation | 5h | C1-C4 | |

**Exit criteria:**
- [ ] `neuralmind serve` launches interactive graph UI
- [ ] Nodes clickable with expand/collapse, type filters, path tracing
- [ ] AI chat uses graph context for grounded answers
- [ ] Bridge mode: CLI and Web share same index
- [ ] Works in browser at localhost:PORT

### Phase D: Advanced Graph Intelligence — 30 hours

**Goal:** Power features for complex codebases.

| Step | Feature | Hours | Dep | Notes |
|------|---------|-------|-----|-------|
| D1 | `trace` — shortest path between two symbols | 8h | existing graph | BFS/DFS on call graph. Return path + intermediate nodes. |
| D2 | `cypher` — raw graph queries | 6h | existing graph | Cypher DSL over graphify. Power user tool. |
| D3 | Cross-repo grouping + contract registry | 10h | D1 | Multi-repo projects. Index once, query across. |
| D4 | `pdg_query` — program dependence graph (taint) | 6h | D1 | Statement-level data/control flow. Security use case. |
| D5 | Tests + doc propagation | 5h | D1-D4 | |

**Exit criteria:**
- [ ] `trace` returns shortest call path between any two symbols
- [ ] `cypher` accepts raw graph queries
- [ ] Cross-repo grouping works for monorepos
- [ ] PDG identifies tainted data flows

---

## 5. Effort Summary

| Phase | Name | Hours | Dep | Priority |
|-------|------|-------|-----|----------|
| A | Safety Net (impact, diff, rename) | 40h | existing | 🔴 P0 |
| B | Zero-Friction Setup (analyze, AGENTS.md) | 25h | - | 🟡 P1 |
| C | Visualization & Exploration (web UI) | 35h | - | 🟡 P1 |
| D | Advanced Graph Intelligence (trace, cypher, PDG) | 30h | A | 🟢 P2 |
| **Total** | | **130h** | | |

### Parallel Tracks

```
Track 1 (Safety):  A → D = 70h (sequential)
Track 2 (Setup):   B = 25h (parallel with A)
Track 3 (Web UI):  C = 35h (parallel with A)

Critical path: A → D = 70h
With parallel: ~8-10 weeks (@ 20h/week, 1 person)
```

---

## 6. What Makes NeuralMind Win

The plan preserves NeuralMind's unique advantages while closing the competitive gap:

| Do Better Than GitNexus | Don't Bother |
|-------------------------|-------------|
| Hebbian synapse learning (unique) | API route mapping (niche) |
| Next-file prediction (unique) | Shape checking (tool overlap) |
| Progressive L0-L3 context (unique) | Tool mapping (meta) |
| MIT license (commercial-friendly) | |
| VS Code extension (unique) | |
| Impact analysis (P0 match) | |
| Coordinated rename (P0 match) | |
| Git-diff detection (P0 match) | |

The strategy: **Don't out-GitNexus GitNexus. Out-learn them.** GitNexus is a static graph.
NeuralMind becomes a graph that LEARKS. That's the moat.

---

*Sources: Ry Walker research, GitHub repo analysis, benchmark reports cited at rywalker.com/research/code-intelligence-tools.*
