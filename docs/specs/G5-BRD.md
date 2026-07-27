# G5 — Structural Gap Detection (InfraNodus-Style Betweenness), Business Requirements Document (BRD)

**Date:** 2026-07-27
**Module:** `neuralmind/structural_gaps.py` + `neuralmind/graphgen.py` + `neuralmind/cli.py`
**Commit:** pending
**Claim tier:** B+ (graph-topological feature borrowed from InfraNodus's Textexture algorithm, novel application to codebases via Louvain communities + betweenness centrality)

---

## 1. Business Problem

NeuralMind indexes codebases into a structural graph (imports, calls, inheritance) and clusters them into Louvain communities. But it has no way to surface what's *missing* — structural blind spots where two communities should connect but don't.

InfraNodus (Nodus Labs, 2011–2026) solves this for text by computing **betweenness centrality** over keyword co-occurrence graphs. High-betweenness nodes that bridge *disconnected* topical clusters represent "content gaps" — ideas the discourse hasn't connected yet. This is InfraNodus's core differentiator (their whitepaper calls it "blind spot detection").

Codebases have the same shape: `auth/` and `billing/` both reference a `User` concept, but if no `user_service.py` bridges them, that's a structural gap — a missing module the codebase likely needs. Today NeuralMind has no mechanism to surface this.

**G5 ports InfraNodus's betweenness-centrality gap detection into NeuralMind's structural graph.** The gap is: NeuralMind *has* the graph + communities, but never analyzes what's *between* them.

---

## 2. Objectives

| # | Objective | Metric |
|---|-----------|--------|
| O1 | Compute betweenness centrality over the structural graph | `compute_betweenness()` returns `{node_id: float}` |
| O2 | Identify cross-community bridge nodes | `find_bridge_candidates()` returns nodes with betweenness ≥ τ in ≥2 communities |
| O3 | Detect structural gaps (high betweenness, low degree) | `detect_gaps()` returns `Gap` list sorted by `gap_score` |
| O4 | Surface gaps via CLI + MCP tool | `neuralmind gaps --structural` + `neuralmind_structural_gaps` MCP tool |
| O5 | Non-destructive, additive | No changes to `build()`, `query()`, `synapses` — reads existing graph |

---

## 3. Requirements

| ID | Requirement | Priority | Test |
|----|-------------|----------|------|
| R1 | `compute_betweenness(graph, normalized=True)` — Brandes algorithm over structural edges | MUST | `test_structural_gaps.py::test_betweenness_star_graph` |
| R2 | `find_bridge_candidates(graph, communities, threshold=0.1)` — nodes appearing in ≥2 community neighborhoods with betweenness ≥ threshold | MUST | `test_bridge_candidates_two_community_graph` |
| R3 | `detect_gaps(graph, communities, top_k=10)` — returns `Gap` list with `gap_score = betweenness * (1 / (degree + 1))` | MUST | `test_detect_gaps_prioritizes_low_degree_bridges` |
| R4 | `Gap` dataclass: `node_id`, `node_name`, `communities`, `betweenness`, `degree`, `gap_score`, `suggested_connections` | MUST | `test_gap_dataclass_fields` |
| R5 | `format_structural_gaps(gaps)` — human-readable report with community pairs + bridge candidates | MUST | `test_format_output_contains_communities` |
| R6 | `cmd_structural_gaps(args)` CLI command — `neuralmind gaps --structural` | MUST | `test_cli_structural_gaps_no_crash` |
| R7 | `neuralmind_structural_gaps` MCP tool (project_path, threshold, top_k) | MUST | `test_mcp_tool_returns_json` |
| R8 | Fail-open on missing/corrupt graph — print warning, return empty | MUST | `test_fail_open_on_missing_graph` |
| R9 | No regressions | MUST | existing test suite green |
| R10 | Pure Python + stdlib — no NetworkX dependency | MUST | `test_no_networkx_import` |

---

## 4. Honest Scope

G5 v1 implements betweenness centrality + bridge detection over the *existing* structural graph. It does NOT implement:

- **Temporal gap tracking** (gap appeared when? is it getting better/worse across builds?)
- **AI-powered gap resolution suggestions** ("you should create `user_service.py`")
- **Integration with synapse store** (bridge candidates feeding spreading activation seeds)
- **Visualization** (Sigma.js graph with gap nodes highlighted — InfraNodus has this, we don't)
- **Incremental betweenness update** (recompute from scratch each call — acceptable for <10K node graphs)

These are documented in `docs/specs/G5-TRD.md` §Future Work.

---

## 5. Gap Score Formula

The gap score is borrowed from InfraNodus's "blind spot" detection and adapted for code:

```
gap_score(v) = betweenness(v) × (1 / (degree(v) + 1))
```

Rationale:
- **Betweenness centrality** — how often node `v` appears on shortest paths between other nodes. High = structural bridge.
- **Inverse degree** — penalizes well-connected hubs (utilities, shared types) that naturally have high betweenness but aren't "missing" — they're already connected.
- **Result** — nodes that bridge communities but have *low* degree score highest. These are the missing connectors.

Example output:
```
## Structural Gaps — betweenness × inverse-degree

1. user_model (communities: auth, billing)  betweenness=0.42  degree=3  gap_score=0.105
   → auth/user.py and billing/invoice.py both reference user_model
   
2. email_validator (communities: auth, notifications)  betweenness=0.31  degree=2  gap_score=0.103
   → auth/signup.py and notifications/mailer.py both import email_validator

3. config_loader (communities: api, worker)  betweenness=0.28  degree=4  gap_score=0.056
```

---

## 6. User Story

```
As a developer working in a large codebase,
I want to find structural gaps — modules that bridge disconnected communities but are under-connected,
So that I can identify missing abstractions, duplicated logic, or architectural blind spots
Without manually tracing import chains.
```

**Acceptance Criteria:**
1. Run `neuralmind gaps --structural` → see ranked list of gap candidates
2. Each candidate shows which communities it bridges + its gap score
3. Results are deterministic (same graph → same gaps)
4. Works on any project with a NeuralMind index (no special config)
5. Fails gracefully if graph is missing

---

## 7. Competitive Analysis (Graph Feature Parity)

| Feature | InfraNodus | NeuralMind (current) | NeuralMind (G5) |
|---------|-----------|---------------------|-----------------|
| Graph construction | Keyword co-occurrence | Structural (AST + edges) | Structural (unchanged) |
| Community detection | Cytoscape/Graphology | Louvain (Phase 1+2) | Louvain (unchanged) |
| Betweenness centrality | ✅ Core feature | ❌ | ✅ |
| Content gap detection | ✅ Blind spot scoring | ❌ | ✅ Gap score |
| Bridge candidates | ✅ Automatic | ❌ | ✅ |
| Visualization | ✅ Sigma.js interactive | ❌ (basic graph view) | ❌ (deferred) |
| Learning/persistence | ❌ None | ✅ Hebbian synapses | ✅ Unchanged |
| MCP tool | ✅ InfraNodus MCP | ❌ | ✅ New |

**Key differentiator retained:** InfraNodus has *no* learning, *no* persistence, *no* synapse store. G5 borrows only the graph-topology insight — NeuralMind's 4-layer progressive disclosure + synapse learning remain unmatched.

---

## 8. Risks & Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Betweenness computation is O(VE) — slow on large graphs | Medium | Slow CLI response | Cap graph size for v1; document incremental approach for future |
| False positives: utilities have high betweenness | High | Noise in gap list | Inverse-degree penalty filters hubs; threshold τ configurable |
| Communities not meaningful on tiny projects | Medium | Misleading gaps | Fail-open: skip gap detection if <3 communities |
| User expects AI suggestions, not just scores | Medium | Disappointment | Scope gap: G5 v1 is detection only; AI suggestions are future work |

---

## 9. Out-of-Scope for G5 v1

| Item | Where it lives | Rationale |
|------|---------------|-----------|
| Temporal gap tracking (gap trends) | Future G6 | Requires persistent gap history store |
| AI-powered gap resolution | Future G6 | Requires LLM integration, prompt engineering |
| Gap visualization in graph view | Future G6 | Requires Sigma.js or similar frontend work |
| Integration with synapse store | Future G6 | Bridge candidates as activation seeds — separate design |
| Incremental betweenness update | Future G6 | Full recompute acceptable for v1 scale |

---

## 10. Timeline

| Phase | Duration | Deliverable |
|-------|----------|-------------|
| Phase 1: Core algorithm | 1 day | `structural_gaps.py` + tests |
| Phase 2: CLI + MCP | 0.5 day | `neuralmind gaps --structural` + MCP tool |
| Phase 3: Docs + co-indexation | 0.5 day | G5-BRD, G5-TRD, G5-TEST-PLAN, `neuralmind build` co-index |

Total: **2 days** from green-light.

---

## 11. Success Criteria

| Criterion | Test | Threshold |
|-----------|------|-----------|
| Gap detection accuracy | Synthetic fixture with known gap | Recall ≥ 0.80 on planted bridges |
| CLI non-crashing | `neuralmind gaps --structural` on fixture | Exit 0, ranked output |
| No regressions | Full test suite | All existing tests pass |
| Deterministic | Run twice on same graph | Identical output |
| Performance | 10K-node synthetic graph | < 5s on modern laptop |

---

## 12. References

- InfraNodus whitepaper (Paranyushkin): betweenness-centrality content gap detection
- Ulrik Brandes (2001): "A Faster Algorithm for Betweenness Centrality" — J. Math. Sociol.
- NeuralMind G3-BRD: Louvain modularity (community detection foundation)
- NeuralMind G4-BRD: Incremental re-extraction (graph stability requirement)

---

*Generated by Hermes. G5-BRD — v1.0. Claim tier: B+. InfraNodus concept port, novel application to codebases.*
