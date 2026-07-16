# BRD — Competitive Response & Learning Moat Advancement

> **Date:** 2026-07-17
> **Status:** DRAFT
> **Owner:** Darren Frost (dfrostar)
> **Reads along:** `COMPARATIVE_ANALYSIS.md`, `docs/brain_like_learning.md`,
> `docs/plans/2026-07-15-enterprise-competition-plan.md`

---

## 1. Business Problem

### 1.1 The Threat

GitNexus has 44k stars, 17 MCP tools, a web UI, and one-command setup. CodeGraph
has 47k stars and SQLite simplicity. Both are growing faster than NeuralMind
(~1.2k stars). Both have **zero** learning capability — they're static graphs.

If NeuralMind closes the feature gap but doesn't advance the learning moat,
competitors will copy our gap-closes and we'll be a me-too graph tool competing
on features alone. We lose the only advantage we have.

### 1.2 The Opportunity

The code intelligence category went vertical in 2026:
- 58-88% fewer tool calls with indexed retrieval
- 97% fewer input tokens vs grep
- Augment Code raised $252M for their context engine

But **no competitor has a learning system**. The entire category is static
graphs and vector search. This is the white space.

### 1.3 The Risk of Standing Still

> "They could build the learning part unless we kept advancing it."

GitNexus/CodeGraph WILL eventually add synapse-style learning. When they do,
NeuralMind's moat disappears. We must advance the learning layer faster than
they can copy the graph layer.

**Hard truth:** A feature Gap-close without Learning advancement = zero durable
moat. We're just buying time until they copy us.

---

## 2. Two Strategic Objectives

### Objective A: Close the Critical Gap (defensive)

Match GitNexus's must-have tools so NeuralMind is no longer a risky choice
for production codebases.

| Priority | Feature | Competitive Parity |
|----------|---------|--------------------|
| 🔴 P0 | Impact analysis (`impact`) | GitNexus #1 most-used tool |
| 🔴 P0 | Git-diff change detection (`detect_changes`) | CI/CD safety |
| 🔴 P0 | Coordinated rename (`rename`) | Refactoring safety |
| 🟡 P1 | Auto setup (`analyze` command) | One-command parity |
| 🟡 P1 | Web UI (interactive graph) | Discovery + onboarding |
| 🟡 P1 | Trace paths (`trace`) | Architecture exploration |
| 🟢 P2 | Raw graph queries (`cypher`) | Power user escape hatch |
| 🟢 P2 | Cross-repo grouping | Monorepo standard |

### Objective B: Advance the Learning Moat (offensive)

Build what GitNexus CANNOT copy without becoming us. Every advance here makes
the moat wider and raises the copying cost.

| Phase | Learning Advance | Why Competitors Can't Easily Copy |
|-------|-----------------|-----------------------------------|
| L1 | **Adaptive synapse decay** — per-project decay rates based on codebase volatility | Requires months of per-project data collection |
| L2 | **Learning transfer across clones** — fork a repo, inherit parent's synapses | Requires org-wide graph + privacy-safe transfer |
| L3 | **Predictive next-edit** — not just next FILE, but next SYMBOL to edit | Requires fine-grained AST-level co-activation data |
| L4 | **Learning-based impact confidence** — "I've seen this change before, here's what happened" | Requires production change history + outcome data |
| L5 | **Auto-generated test suggestions** based on synapse-refined impact | Requires synapse + graph + test-outcome feedback |

**Rule of thumb:** Every dollar spent on Objective B is worth 3x the same
dollar spent on Objective A. Objective A keeps us in the game. Objective B
wins it.

---

## 3. Feature Requirements (Objective A — Gap Close)

### 3.1 Impact Analysis (P0)

**User story:** As an AI agent developer, before I edit a function, I want to
know what breaks if I change it — so I don't ship blind edits.

**Acceptance criteria:**
- [ ] Given a symbol, return all upstream dependents (callers, importers)
- [ ] Group by depth (direct → transitive → edge)
- [ ] Confidence score per impact (high = definitely breaks, low = maybe)
- [ ] Response time <500ms for codebases up to 1M LOC
- [ ] MCP tool + CLI command

**Benchmarks to beat:**
- GitNexus: 88% fewer tool calls via impact analysis
- Target for NM: 90%+ fewer calls (match or beat)

### 3.2 Git-Diff Change Detection (P0)

**User story:** As a developer reviewing a commit, I want to know what
processes/functions are affected by the changed lines — so I understand
blast radius before merging.

**Acceptance criteria:**
- [ ] Accept git diff / commit range as input
- [ ] Map changed lines → AST nodes → graph symbols
- [ ] Return affected symbols grouped by severity (direct/indirect/none)
- [ ] Works with `git diff HEAD~1`, `git diff commit1..commit2`, uncommitted changes
- [ ] MCP tool + CLI command

### 3.3 Coordinated Rename (P0)

**User story:** As a developer refactoring, I want to rename a symbol across
the codebase WITHOUT breaking references — so I can refactor safely.

**Acceptance criteria:**
- [ ] Find all references via graph (not just text search)
- [ ] Group by file, show preview of each change
- [ ] Execute atomic rename (all-or-nothing)
- [ ] Verify no broken refs post-rename
- [ ] Handle imports, re-exports, dynamic refs
- [ ] MCP tool + CLI command

### 3.4 Auto Setup (P1)

**User story:** As a new user, I want ONE command to index my repo, register
hooks, and create context files — so I never read a setup guide.

**Acceptance criteria:**
- [ ] `neuralmind analyze` does: index graph + install hooks + create AGENTS.md + verify MCP
- [ ] Auto-detect agent (Claude Code, Cursor, Codex, Cline, Continue)
- [ ] Generate AGENTS.md with: architecture summary, key files, conventions, entry points
- [ ] Works on monorepos (detect sub-projects, index each)
- [ ] Idempotent — safe to re-run

### 3.5 Web UI (P1)

**User story:** As a developer exploring a new codebase, I want an interactive
graph visualization so I can understand architecture faster than reading files.

**Acceptance criteria:**
- [ ] `neuralmind serve` launches React-based graph UI
- [ ] Interactive: click to expand, collapse, trace paths
- [ ] Filter by node type (function, class, module, file, type)
- [ ] Search bar with graph-grounded results
- [ ] AI chat panel (RAG over graph)
- [ ] Bridge mode: CLI-indexed repos appear without re-upload

### 3.6 Trace Paths (P1)

**User story:** As an agent exploring an unfamiliar codebase, I want to know
the call path between two symbols — so I understand data/control flow.

**Acceptance criteria:**
- [ ] Given source + target symbol, return shortest path
- [ ] Include intermediate nodes with edge types (calls, imports, extends)
- [ ] Support directed and undirected search
- [ ] MCP tool + CLI command

---

## 4. Learning Advancement Requirements (Objective B)

### 4.1 L1: Adaptive Synapse Decay

**Current state:** Synapses decay at a global rate.

**Problem:** Fast-moving codebases (startups) need fast decay. Stable
codebases (legacy) need slow decay. One rate doesn't fit all.

**Requirement:** Calculate per-project decay rate based on:
- Commit frequency (more commits → faster decay)
- Change volatility (files that change a lot → faster decay)
- Synapse age half-life

**Metric:** 20% better relevance ranking on cross-project benchmarks.

### 4.2 L2: Learning Transfer Across Clones

**Current state:** Forking a repo means starting from zero synapses.

**Problem:** Enterprise teams have dozens of microservice clones. Losing learned
associations on fork = wasted context.

**Requirement:**
- Synapses exportable as a "brain dump" (anonymized graph)
- Fork imports parent graph, starts with parent's associations
- Privacy-safe: no code leaves premises, only edge weights + structure
- Opt-in per org

**Metric:** New repo onboarding time reduced by 50% for orgs with >10 repos.

### 4.3 L3: Predictive Next-Edit (Symbol-Level)

**Current state:** `next_likely` predicts next FILE.

**Problem:** Agents need symbol-level granularity. "Next file" is too coarse
for large files (>1000 LOC).

**Requirement:**
- Predict next SYMBOL (function/class/method) the developer will edit
- Based on synapse chains: if editing A, and A co-activates with B, predict B
- Integrate with L0-L3 context: pre-load B's context when prediction confidence >70%

**Metric:** 60%+ accuracy on next-symbol prediction (vs ~35% for file-level).

### 4.4 L4: Learning-Based Impact Confidence

**Current state:** Impact analysis uses only structural graph.

**Problem:** Structural "what calls this" misses historical "what broke last
time we changed this" — which is MORE informative.

**Requirement:**
- When `impact` shows results, cross-reference with synapse history
- If this symbol changed before and we have outcome data, boost confidence
- "Last 3 edits to this function broke tests X, Y, Z" as annotation
- Learn from CI/test outcomes (connect to GitHub Actions, etc.)

**Metric:** 40% improvement in impact precision (fewer false positives).

### 4.5 L5: Auto-Generated Test Suggestions

**Current state:** Not built.

**Problem:** The reason you need impact analysis is to know what to test. But
impact alone says "what breaks" — not "how to verify it still works."

**Requirement:**
- Given an edit, `impact` returns affected symbols
- `suggest_tests` takes impact + returns relevant test files/functions
- Synapse layer boosts: "tests A and B usually run after edits like this"
- Given test outcome (pass/fail), feed back into synapse layer

**Metric:** 70%+ of relevant tests identified for a given change.

---

## 5. Success Metrics

### 5.1 Competitive Parity Metrics (Objective A)

| Metric | Target | Measurement |
|--------|--------|-------------|
| Impact response time | <500ms for 1M LOC | Benchmark suite |
| Rename safety | 0 broken refs in 100-file test | Automated test |
| Setup friction | <2 min from install to first query | User timing study |
| Web UI engagement | >50% of users run `serve` | Anonymous opt-in |

### 5.2 Learning Moat Metrics (Objective B)

| Metric | Target | Measurement |
|--------|--------|-------------|
| Synapse relevance | +20% vs static graph | Cross-project benchmark |
| Onboarding lift | 50% faster for orgs >10 repos | Org pilot measurement |
| Next-edit accuracy | 60%+ symbol-level | Prediction benchmark |
| Impact precision | +40% with historical data | CI outcome correlation |
| Test suggestion recall | 70%+ relevant tests | Test correlation study |

---

## 6. Non-Goals

| Feature | Reason |
|---------|--------|
| API route mapping | Niche, only for web frameworks |
| Shape checking (API contracts) | Overlap with OpenAPI/Zod/Swagger |
| MCP tool mapping (meta-tooling) | Tiny addressable market |
| Cloud-hosted graph | Violates zero-code-egress moat |
| Windows-native binary | Low user demand, high maintenance |
| IDE integrations beyond VS Code | Insufficient ROI vs VS Code extension |

---

## 7. Roadmap Summary

| Quarter | Focus | Key Deliverables | Hours |
|---------|-------|------------------|-------|
| Q3 2026 | A: P0 Safety Net | impact, detect_changes, rename | 40h |
| Q3 2026 | B: L1 Learning | Adaptive synapse decay | 15h |
| Q4 2026 | A: P1 Experience | analyze, web UI, trace | 60h |
| Q4 2026 | B: L2+L3 Learning | Clone transfer, next-symbol | 30h |
| Q1 2027 | A: P2 Power | cypher, cross-repo, PDG | 30h |
| Q1 2027 | B: L4+L5 Learning | Impact confidence, test suggestions | 35h |
| **Total** | | | **210h** |

### Effort Allocation

| Objective | Hours | % of Total |
|-----------|-------|------------|
| A: Gap Close (defensive) | 130h | 62% |
| B: Learning Moat (offensive) | 80h | 38% |

**Ratio philosophy:** 60% defense keeps us competitive. 40% offense builds the
durable moat. As learning matures, ratio should flip to 40/60 by Q1 2027.

---

*End of BRD — Competitive Response & Learning Moat Advancement*
