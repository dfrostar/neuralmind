# TRD — Competitive Response & Learning Moat Advancement

> **Date:** 2026-07-17
> **Status:** DRAFT
> **Owner:** Darren Frost (dfrostar)
> **Implements:** BRD `2026-07-17-brd-competitive-response.md`

---

## 1. Architecture Overview

### 1.1 Current System

```
                    ┌─────────────────────────────────────┐
                    │          MCP Clients                │
                    │  Claude Code, Cursor, Codex, Cline  │
                    └──────────────┬──────────────────────┘
                                   │ MCP Protocol
                    ┌──────────────▼──────────────────────┐
                    │       MCP Server (mcp_server.py)     │
                    │  14 tools · RBAC security · routing │
                    └──────────────┬──────────────────────┘
                                   │
                    ┌──────────────▼──────────────────────┐
                    │        Core Engine (core.py)          │
                    │  Query planner · result assembler    │
                    └──┬──────────┬──────────┬─────────────┘
                       │          │          │
            ┌──────────▼──┐  ┌────▼─────┐  ┌▼──────────────┐
            │ Graph Layer  │  │ Synapse  │  │ Context       │
            │ (graphify)   │  │ Layer    │  │ Selector      │
            │ Symbol graph │  │ (SQLite) │  │ (L0-L3)       │
            │ Call graph   │  │ Hebbian  │  │ Progressive   │
            │ Embeddings   │  │ weights  │  │ disclosure    │
            │ (ChromaDB)   │  │ Decay    │  │               │
            └──────────────┘  └──────────┘  └───────────────┘
                       │          │          │
                    ┌──────────▼──────────▼──────────┐
                    │     File Watcher (watcher.py)   │
                    │  Change events → co-activation  │
                    └────────────────────────────────┘
```

### 1.2 Target Architecture (post-build)

```
                    ┌─────────────────────────────────────┐
                    │          MCP Clients                │
                    │  Claude Code, Cursor, Codex, Cline  │
                    └──────────────┬──────────────────────┘
                                   │ MCP Protocol
                    ┌──────────────▼──────────────────────┐
                    │       MCP Server (mcp_server.py)     │
                    │  20+ tools · RBAC · Skills · Hooks  │
                    └──────────────┬──────────────────────┘
                                   │
                    ┌──────────────▼──────────────────────┐
                    │        Core Engine (core.py)          │
                    │  NEW: Impact engine, path tracer     │
                    │  NEW: Git-diff mapper, rename coord  │
                    └──┬──────────┬──────────┬─────────────┘
                       │          │          │
            ┌──────────▼──┐  ┌────▼─────┐  ┌▼──────────────┐
            │ Graph Layer  │  │ Synapse  │  │ Context       │
            │ SAME         │  │ ENHANCED │  │ ENHANCED      │
            │              │  │ Adaptive │  │ L0-L3 +       │
            │              │  │ decay    │  │ pre-load      │
            │              │  │ Transfer │  │ on prediction │
            │              │  │ Symbol   │  │               │
            └──────────────┘  │ predict  │  └───────────────┘
                       │      └──────────┘          │
                       │          │                  │
                    ┌──────────▼──────────▼──────────▼─────────┐
                    │          File Watcher (watcher.py)        │
                    │  SAME: change events → co-activation      │
                    │  NEW: git-diff hooks, CI outcome feedback │
                    └──────────────────────────────────────────┘
                                   │
                    ┌──────────────▼──────────────────────┐
                    │     Web UI (new: React + D3)         │
                    │  Graph viz · AI chat · bridge mode   │
                    └─────────────────────────────────────┘
```

---

## 2. Objective A: Gap-Close Technical Design

### 2.1 Impact Analysis (`impact`)

**Inputs:** `symbol: str`, `depth: int = 3`, `include_tests: bool = True`

**Output:**
```json
{
  "symbol": "authService.verifyToken",
  "total_impact": 47,
  "depths": {
    "1": {"count": 5, "symbols": ["..."]},
    "2": {"count": 12, "symbols": ["..."]},
    "3": {"count": 30, "symbols": ["..."]}
  },
  "confidence": {
    "high": ["..."],
    "medium": ["..."],
    "low": ["..."]
  },
  "historical": [
    {"commit": "abc123", "changed": "...", "outcome": "tests_failed: 2"},
  ]
}
```

**Implementation:**
1. Walk the graph upward from symbol (callers → callers of callers)
2. Group by BFS depth
3. Cross-reference synapse layer for historical strength (adaptive confidence)
4. If L4 learning present, annotate with past outcome data
5. Cache results per symbol per commit hash (invalidated on change)

**Performance requirement:** <500ms for 1M LOC → iterative BFS with caching + early exit at depth limit.

**Files touched:**
- `neuralmind/mcp_server.py` — new `tool_impact` function
- `neuralmind/impact_engine.py` — new module
- `neuralmind/core.py` — integrate impact cache

### 2.2 Git-Diff Change Detection (`detect_changes`)

**Inputs:** `commit_range: str | None`, `include_uncommitted: bool = True`

**Output:**
```json
{
  "changes": [
    {
      "file": "src/auth.ts",
      "lines": "45-67",
      "affected_symbols": ["authService.verifyToken"],
      "severity": "direct",
      "downstream_impact": 12
    }
  ]
}
```

**Implementation:**
1. Run `git diff --unified=0 <range>` → extract changed line ranges per file
2. Parse changed files with tree-sitter → extract AST nodes at line ranges
3. Map AST nodes to graph symbols (using existing indexer)
4. For each affected symbol, call impact engine (reuse 2.1)
5. Return severity-ranked results

**Files touched:**
- `neuralmind/mcp_server.py` — new `tool_detect_changes`
- `neuralmind/git_diff_mapper.py` — new module
- Reuse `impact_engine.py` from 2.1

### 2.3 Coordinated Rename (`rename`)

**Inputs:** `symbol: str`, `new_name: str`, `dry_run: bool = True`

**Output:**
```json
{
  "symbol": "authService.verifyToken",
  "new_name": "authService.verifyAccessToken",
  "files_affected": 8,
  "total_refs": 23,
  "preview": [
    {"file": "src/auth.ts", "line": 45, "old": "verifyToken", "new": "verifyAccessToken"},
    ...
  ],
  "status": "success|conflict",
  "broken_refs_post": 0
}
```

**Implementation:**
1. Find all references via graph (not text search — handle imports, re-exports, dynamic refs)
2. Group by file, generate preview
3. Atomic execution: write all files, or none
4. Post-rename verification: run `impact` on new symbol, ensure no broken refs
5. Rollback on conflict (restore all files)

**Files touched:**
- `neuralmind/mcp_server.py` — new `tool_rename`
- `neuralmind/rename_coordinator.py` — new module
- Reuse `impact_engine.py` for verification

### 2.4 Auto Setup (`analyze`)

**Implementation:**
1. Detect agent type by scanning config files (`.claude/`, `.cursor/`, `.continue/`)
2. Run `build` if no existing index
3. Detect hooks dir, install hooks for detected agent
4. Scan graph for entry points, modules, conventions → generate AGENTS.md
5. Write MCP config to detected agent's config
6. Verify connectivity → report success/failure

**Files touched:**
- `neuralmind/cli.py` — new `cmd_analyze` subcommand
- `neuralmind/auto_setup.py` — new module
- `neuralmind/agents_md_generator.py` — new module

### 2.5 Web UI

**Stack:** React + TypeScript + D3.js (force-directed graph) + Vite

**Structure:**
```
neuralmind/webui/
├── index.html
├── src/
│   ├── App.tsx          # Main layout: search bar + graph + chat
│   ├── GraphView.tsx    # D3 force-directed graph renderer
│   ├── SearchPanel.tsx  # Typeahead search with graph results
│   ├── ChatPanel.tsx    # AI chat with graph-grounded RAG
│   ├── SymbolDetail.tsx # Click a node → show 360° context
│   └── bridge.ts        # SSE connect to local CLI server
├── package.json
└── vite.config.ts
```

**API contract (server-side):**
```
GET  /api/graph/{project}           → full graph JSON (paginated)
GET  /api/graph/{project}/search?q= → search results
GET  /api/graph/{project}/node/{id} → 360° symbol context
POST /api/chat/{project}            → graph-grounded RAG chat
GET  /api/events                    → SSE stream of graph changes
WS   /api/bridge                    → CLI↔Web sync
```

**Bridge mode:** CLI `watch` already emits events via `event_bus.py`. Web UI
subscribes, renders live graph updates.

**Files touched:**
- `neuralmind/webui/` — new directory
- `neuralmind/server.py` — extend with REST + WebSocket endpoints
- `neuralmind/mcp_server.py` — new `tool_serve` to launch web UI

### 2.6 Trace Paths (`trace`)

**Inputs:** `from_symbol: str`, `to_symbol: str`, `max_depth: int = 10`

**Implementation:**
1. Build directed graph of calls/imports
2. Run BFS/Dijkstra from `from_symbol` to `to_symbol`
3. Return path with edge types, intermediate nodes
4. Support directed (caller→callee) and undirected

**Files touched:**
- `neuralmind/mcp_server.py` — new `tool_trace`
- Reuse graph layer

---

## 3. Objective B: Learning Moat Technical Design

### 3.1 L1: Adaptive Synapse Decay

**Current:** Global decay rate applied uniformly.

**New design:**
```python
class AdaptiveDecay:
    def calculate_base_rate(self, project: Project) -> float:
        """Calculate codebase-specific decay rate."""
        commit_velocity = self._avg_commits_per_week(project)
        file_churn = self._file_churn_rate(project)
        age_half_life = self._synapse_age_distribution(project)

        # Fast-moving = faster decay (0.15/week)
        # Slow-moving = slower decay (0.03/week)
        base = clamp(0.03 + (commit_velocity * 0.02) + (file_churn * 0.05), 0.03, 0.15)

        # Adjust half-life: older synapses resist decay more
        return base * self._age_resistance_factor(age_half_life)

    def apply(self, synapse: Synapse, project: Project) -> float:
        rate = self.calculate_base_rate(project)
        # Per-project rate overrides global
        return synapse.strength * (1 - rate) ** synapse.age_weeks
```

**Files touched:**
- `neuralmind/synapses.py` — new `AdaptiveDecay` class
- `neuralmind/watcher.py` — emit commit velocity metrics
- Backward compatible: global rate remains default, adaptive is opt-in via
  `NEURALMIND_ADAPTIVE_DECAY=1`

### 3.2 L2: Learning Transfer Across Clones

**Design:**
```python
class SynapseTransfer:
    def export_brain(self, project: Project, anonymize: bool = True) -> BrainDump:
        """Export synapses with optional anonymization."""
        synapses = self._get_all_synapses(project)
        if anonymize:
            # Replace symbol names with structural hashes
            synapses = [(hash_symbol(s), hash_symbol(t), w) for s, t, w in synapses]
        return BrainDump(synapses, metadata=self._get_metadata(project))

    def import_brain(self, project: Project, dump: BrainDump) -> None:
        """Import synapses from parent repo."""
        for source, target, weight in dump.synapses:
            # Map structural hashes back to local symbols
            local_source = self._resolve_hash(source, project)
            local_target = self._resolve_hash(target, project)
            if local_source and local_target:
                self._create_synapse(local_source, local_target, weight * 0.7)  # discount 30%
```

**Privacy guarantee:** Only edge weights + structural patterns leave the machine.
No code, no symbol names, no content. Mathematical skeleton only.

**Files touched:**
- `neuralmind/synapses.py` — new `SynapseTransfer` class
- `neuralmind/mcp_server.py` — new `tool_export_brain`, `tool_import_brain`

### 3.3 L3: Predictive Next-Edit (Symbol-Level)

**Current:** `next_likely` returns next FILE.

**New design:**
```python
class SymbolPredictor:
    def predict_next_symbol(self, current_symbol: str, top_k: int = 5) -> list[PredictedSymbol]:
        """Predict which symbol the developer will edit next."""
        # 1. Get synapse neighbors (current signal)
        neighbors = self.synapses.get_neighbors(current_symbol)

        # 2. Get graph neighbors (structural signal)
        graph_neighbors = self.graph.get_callees(current_symbol) + self.graph.get_callers(current_symbol)

        # 3. Combine with synapse-weighted scores
        candidates = {}
        for n in graph_neighbors:
            candidates[n] = self._structural_weight(n)
        for n, strength in neighbors:
            candidates[n] = candidates.get(n, 0) + strength * 2.0  # synapse boost

        # 4. Context sequence (what symbols follow this one in edit history)
        sequence_score = self._edit_sequence_score(current_symbol)
        for n, score in sequence_score.items():
            candidates[n] = candidates.get(n, 0) + score * 1.5

        return sorted(candidates, key=candidates.get, reverse=True)[:top_k]
```

**Integration with context selector:** When prediction confidence > 70%,
automatically pre-load L1 context for predicted symbol into working memory.

**Files touched:**
- `neuralmind/synapses.py` — new `SymbolPredictor` class
- `neuralmind/mcp_server.py` — new `tool_predict_symbol`
- `neuralmind/context_selector.py` — pre-load hook

### 3.4 L4: Learning-Based Impact Confidence

**Design:** After `impact` returns structural results, cross-reference with
synapse history to boost confidence.

```python
class HistoricalImpact:
    def annotate_impact(self, impact_result: ImpactResult, project: Project) -> ImpactResult:
        """Add historical confidence to structural impact."""
        for symbol in impact_result.all_symbols:
            # Have we seen this symbol change before?
            history = self.synapses.get_change_outcomes(symbol, project)
            if history:
                actual_breaks = [h for h in history if h.outcome == "test_false"]
                false_positives = [h for h in history if h.outcome == "test_passed"]

                if len(actual_breaks) > len(false_positives):
                    impact_result.confidence[symbol] = "high"
                    impact_result.historical_note[symbol] = (
                        f"Last {len(history)} edits: {len(actual_breaks)} broke tests"
                    )
                else:
                    impact_result.confidence[symbol] = "low"
                    impact_result.historical_note[symbol] = (
                        f"Last {len(history)} edits: survived {len(false_positives)}"
                    )
        return impact_result
```

**CI outcome feedback loop:**
1. Connect to GitHub Actions (opt-in)
2. When tests fail after an edit, mark impact predictions as "validated" or "false_positive"
3. Feed back into synapse layer: strengthen synapses for validated, weaken for false positive

**Files touched:**
- `neuralmind/impact_engine.py` — `HistoricalImpact` class
- `neuralmind/ci_feedback.py` — new module (optional, opt-in)

### 3.5 L5: Auto-Generated Test Suggestions

**Design:**
```python
class TestSuggester:
    def suggest_tests(self, impact_result: ImpactResult) -> list[TestSuggestion]:
        """Find tests that cover affected symbols."""
        suggestions = []
        for symbol in impact_result.all_symbols:
            # Find tests that reference this symbol
            test_files = self.graph.get_test_files_for_symbol(symbol)
            for test_file in test_files:
                relevance = self.synapses.get_test_relevance(test_file, symbol)
                suggestions.append(TestSuggestion(
                    file=test_file,
                    symbols_covered=[symbol],
                    relevance=relevance,
                    synapse_boost=self.synapses.get_historical_test_strength(test_file)
                ))
        return sorted(suggestions, key=lambda s: s.relevance + s.synapse_boost, reverse=True)
```

**Files touched:**
- `neuralmind/mcp_server.py` — new `tool_suggest_tests`
- `neuralmind/test_suggester.py` — new module

---

## 4. Data Model Changes

### 4.1 Synapse Table Extension

```sql
-- Current synapses table
CREATE TABLE IF NOT EXISTS synapses (
    id INTEGER PRIMARY KEY,
    source_symbol TEXT NOT NULL,
    target_symbol TEXT NOT NULL,
    strength REAL NOT NULL DEFAULT 0.5,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_activated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- New columns for L1-L5
ALTER TABLE synapses ADD COLUMN project_id TEXT;           -- For per-project decay
ALTER TABLE synapses ADD COLUMN decay_rate REAL;           -- Project-specific rate
ALTER TABLE synapses ADD COLUMN age_weeks INTEGER DEFAULT 0;
ALTER TABLE synapses ADD COLUMN symbol_type TEXT;          -- 'function' | 'class' | 'module'
ALTER TABLE synapses ADD COLUMN change_outcome TEXT;       -- 'passed' | 'failed' | 'manual'
ALTER TABLE synapses ADD COLUMN is_anonymized INTEGER DEFAULT 0;  -- For transfer
```

### 4.2 New Tables

```sql
-- Per-project metadata
CREATE TABLE IF NOT EXISTS project_meta (
    id INTEGER PRIMARY KEY,
    project_path TEXT UNIQUE,
    commit_velocity REAL,          -- commits/week
    file_churn_rate REAL,          -- fraction of files changed/week
    base_decay_rate REAL,          -- calculated
    last_analyzed TIMESTAMP
);

-- CI outcome tracking (opt-in)
CREATE TABLE IF NOT EXISTS ci_outcomes (
    id INTEGER PRIMARY KEY,
    commit_hash TEXT,
    symbol TEXT,
    test_file TEXT,
    outcome TEXT,                  -- 'passed' | 'failed' | 'skipped'
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Brain dumps for transfer
CREATE TABLE IF NOT EXISTS brain_dumps (
    id INTEGER PRIMARY KEY,
    source_project TEXT,
    created_at TIMESTAMP,
    synapse_count INTEGER,
    anonymized INTEGER,
    data BLOB                     -- serialized BrainDump
);
```

---

## 5. API / Tool Signatures

### 5.1 New MCP Tools

| Tool Name | Inputs | Output | Dep |
|-----------|--------|--------|-----|
| `neuralmind_impact` | `symbol`, `depth?`, `include_tests?` | ImpactResult JSON | graph + synapses |
| `neuralmind_detect_changes` | `commit_range?`, `include_uncommitted?` | ChangeImpact[] | git + impact engine |
| `neuralmind_rename` | `symbol`, `new_name`, `dry_run?` | RenameResult | impact engine + graph |
| `neuralmind_trace` | `from_symbol`, `to_symbol`, `max_depth?` | PathResult | graph |
| `neuralmind_analyze` | `project_path?` | SetupResult | auto_setup module |
| `neuralmind_predict_symbol` | `current_symbol`, `top_k?` | SymbolPrediction[] | synapses + graph |
| `neuralmind_export_brain` | `project_path`, `anonymize?` | BrainDump JSON | synapses |
| `neuralmind_import_brain` | `project_path`, `dump` | ImportResult | synapses |
| `neuralmind_suggest_tests` | `impact_result` | TestSuggestion[] | graph + synapses |

**Total after implementation:** 14 existing + 9 new = **23 MCP tools** (vs GitNexus's 17).

### 5.2 New CLI Commands

| Command | Description | Dep |
|---------|-------------|-----|
| `neuralmind analyze` | Full auto-setup for a project | auto_setup |
| `neuralmind impact <symbol>` | CLI wrapper for impact tool | impact_engine |
| `neuralmind detect-changes` | CLI wrapper for diff tool | git_diff_mapper |
| `neuralmind rename <old> <new>` | CLI wrapper for rename | rename_coordinator |
| `neuralmind trace <from> <to>` | CLI wrapper for path tracer | graph |
| `neuralmind predict-symbol <current>` | CLI wrapper for predictor | synapses |
| `neuralmind brain-export` | Export synapses for transfer | synapses |
| `neuralmind brain-import <dump>` | Import synapses from transfer | synapses |
| `neuralmind test-suggest` | Suggest tests for impact | test_suggester |

---

## 6. Module Dependency Graph

```
mcp_server.py
    ├── core.py
    │   ├── impact_engine.py (NEW)
    │   │   ├── graphify (existing)
    │   │   ├── synapses.py (existing)
    │   │   └── historical_impact.py (NEW, L4)
    │   ├── git_diff_mapper.py (NEW)
    │   │   └── impact_engine.py
    │   ├── rename_coordinator.py (NEW)
    │   │   └── impact_engine.py
    │   ├── path_tracer.py (NEW)
    │   │   └── graphify
    │   ├── auto_setup.py (NEW)
    │   │   └── core.py
    │   ├── agents_md_generator.py (NEW)
    │   │   └── core.py
    │   └── test_suggester.py (NEW, L5)
    │       ├── graphify
    │       └── synapses.py
    ├── synapses.py (ENHANCED)
    │   ├── adaptive_decay.py (NEW, L1)
    │   ├── synapse_transfer.py (NEW, L2)
    │   ├── symbol_predictor.py (NEW, L3)
    │   └── ci_feedback.py (NEW, L4)
    └── webui/ (NEW)
        ├── server.py (extended)
        └── static/ (React app)
```

---

## 7. Testing Strategy

### 7.1 Unit Tests

| Module | Coverage | Key Tests |
|--------|----------|-----------|
| `impact_engine.py` | 85%+ | Known graph → expected impact, depth limits, confidence scoring |
| `git_diff_mapper.py` | 80%+ | Known diff → expected symbols, severity ranking |
| `rename_coordinator.py` | 85%+ | Multi-file rename, atomicity, rollback on conflict |
| `adaptive_decay.py` | 80%+ | Fast vs slow project rates, per-project overrides |
| `synapse_transfer.py` | 80%+ | Export→import roundtrip, anonymization correctness |
| `symbol_predictor.py` | 75%+ | Edit sequence prediction, top-k accuracy |

### 7.2 Integration Tests

| Scenario | Tools Involved | Expected |
|----------|---------------|----------|
| Edit a function and check impact | `impact` → `detect_changes` | Consistent results |
| Rename a function end-to-end | `rename` → `impact` verify | Zero broken refs |
| Pre-load prediction | `predict_symbol` → L1 context | <100ms load time |
| CI feedback loop | `detect_changes` → CI → synapse update | Synapse strength adjusts |

### 7.3 Benchmark Requirements

| Benchmark | Target | How Measured |
|-----------|--------|--------------|
| Impact response | <500ms for 1M LOC | `pytest-benchmark` on synthetic codebase |
| Rename speed | <2s for 100 files | Atomic rename test |
| Prediction accuracy | 60%+ symbol-level | Edit-history replay benchmark |
| Web UI render | <3s for 5k-node graph | Synthetic large graph test |

---

## 8. Release Phasing

### 8.1 Release v0.44.0 — Safety Net (Q3 2026)

| Feature | Hours |
|---------|-------|
| `impact` tool | 12h |
| `detect_changes` tool | 10h |
| `rename` tool | 10h |
| Tests + docs | 8h |
| **Subtotal** | **40h** |

### 8.2 Release v0.45.0 — Learning L1 (Q3 2026)

| Feature | Hours |
|---------|-------|
| Adaptive synapse decay | 10h |
| Per-project decay rates | 5h |
| **Subtotal** | **15h** |

### 8.3 Release v0.46.0 — Experience (Q4 2026)

| Feature | Hours |
|---------|-------|
| `analyze` auto-setup | 8h |
| AGENTS.md generation | 6h |
| `trace` paths | 6h |
| Tests + docs | 5h |
| **Subtotal** | **25h** |

### 8.4 Release v0.47.0 — Web UI (Q4 2026)

| Feature | Hours |
|---------|-------|
| Web UI scaffold | 12h |
| Graph rendering | 10h |
| AI chat panel | 8h |
| Bridge mode | 5h |
| Tests + docs | 5h |
| **Subtotal** | **40h** |

### 8.5 Release v0.48.0 — Learning L2+L3 (Q4 2026)

| Feature | Hours |
|---------|-------|
| Clone transfer | 12h |
| Symbol-level prediction | 12h |
| Context pre-load | 6h |
| **Subtotal** | **30h** |

### 8.6 Release v0.49.0 — Power (Q1 2027)

| Feature | Hours |
|---------|-------|
| `cypher` raw queries | 6h |
| Cross-repo grouping | 10h |
| PDG / taint analysis | 10h |
| Tests + docs | 5h |
| **Subtotal** | **31h** |

### 8.7 Release v0.50.0 — Learning L4+L5 (Q1 2027)

| Feature | Hours |
|---------|-------|
| Historical impact confidence | 12h |
| CI feedback loop | 8h |
| Test suggestions | 10h |
| Tests + docs | 5h |
| **Subtotal** | **35h** |

---

## 9. Risks & Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Impact engine too slow on 1M+ LOC | P0 failure | Iterative BFS + caching + early exit |
| Rename breaks code | Safety failure | Atomic execution + post-verify + rollback |
| Adaptive decay overfits | Learning failure | Default-off, A/B test before enabling |
| Web UI bundle too big | Slow load | Code-split, lazy load, compress |
| Clone transfer leaks info | Privacy failure | Structural hashing + opt-in only |
| CI feedback loop noise | Learning pollution | Require manual approval per connection |
| Synapse DB grows unbounded | Storage failure | Decay applies to DB size + prune threshold |

---

## 10. Open Questions

1. **Scope of Web UI for v0.47?** Full React app vs lightweight HTML+JS?
2. **CI feedback: GitHub Actions first?** GitLab/Bitbucket later?
3. **Anonymization standard for brain dumps?** Custom vs differential privacy?
4. **Scope of PDG?** Tree-sitter level vs full compiler-level?
5. **Should `analyze` be the default entry point?** Replace `build`?

---

*End of TRD — Competitive Response & Learning Moat Advancement*
