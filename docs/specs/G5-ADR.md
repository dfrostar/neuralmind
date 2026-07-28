# G5 — Architecture Decision Records (ADRs)

**Date:** 2026-07-27
**Module:** `neuralmind/structural_gaps.py` + `neuralmind/cli.py` + `neuralmind/mcp_server.py`
**Commit:** pending
**Claim tier:** B+

---

## ADR-001: Betweenness Centrality Over Other Centrality Measures

### Status: Accepted

### Context

InfraNodus's core differentiator is "blind spot detection" — identifying nodes that bridge disconnected communities. We need a graph metric to quantify how critical a node is as a bridge.

Options considered:

| Metric | What it measures | Complexity | Suitability for bridges |
|--------|-----------------|------------|------------------------|
| **Betweenness centrality** | Fraction of shortest paths passing through a node | O(VE) | ✅ Excellent — directly measures bridge criticality |
| Degree centrality | Number of direct neighbors | O(V) | ❌ Measures hub-ness, not bridging |
| Eigenvector centrality | Influence based on neighbors' influence | O(V²) | ❌ Measures popularity, not bridging |
| Closeness centrality | Average distance to all other nodes | O(V·E) | ⚠️ Related but doesn't isolate bridges |
| PageRank | Random-walk importance | O(V·E) | ❌ Measures authority, not bridging |

### Decision

Use **betweenness centrality** (Brandes algorithm). It directly answers the question we care about: "which nodes are critical bridges between otherwise disconnected parts of the codebase?"

### Consequences

- **Positive:** Directly measures bridge criticality. Matches InfraNodus's proven approach. Easy to explain.
- **Negative:** O(VE) complexity — slow on very large graphs (>10K nodes).
- **Mitigation:** Sampling for large graphs (k-approximate betweenness). Cap at MAX_BETWEENNESS_NODES=5K.

### Trade-off metric

Betweenness correctness vs runtime. For a 5K-node graph: ~2.5×10⁸ operations worst case, ~3s on modern laptop. Acceptable for a CLI tool (not in the critical query path).

---

## ADR-002: Brandes Algorithm vs Approximate Betweenness

### Status: Accepted

### Context

Exact betweenness centrality via Brandes algorithm is O(VE). For large graphs, approximate methods exist:

| Method | Complexity | Accuracy | Implementation |
|--------|-----------|----------|----------------|
| **Brandes (exact)** | O(VE) | 100% | ~80 lines pure Python |
| K-approximate (sample k sources) | O(k·E) | ~95% with k=√V | ~100 lines |
| Randomized approximate (floats) | O(k·E) | ~90% | ~120 lines |
| NetworkX built-in | C bindings | 100% | External dependency |

### Decision

Use **Brandes exact algorithm** for v1. Fall back to k-approximate sampling only when V > MAX_BETWEENNESS_NODES (default 5K).

Rationale: Exact results matter for a gap detector — false positives (ranking a non-gap as a gap) erode trust. Brandes is O(VE) but our graphs are small (<10K nodes typical). The fallback handles pathological cases.

### Consequences

- **Positive:** Exact results. No accuracy loss. Pure Python (no C deps).
- **Negative:** O(VE) worst case.
- **Mitigation:** Sampling fallback for large graphs.

---

## ADR-003: Pure Python Implementation vs NetworkX

### Status: Accepted

### Context

NetworkX has a `betweenness_centrality()` implementation in C via `graph-tool` or in pure Python. But NetworkX is a 200+ MB dependency with many transitive deps.

Options:

| Approach | Dependency | Binary size | Performance |
|----------|-----------|-------------|-------------|
| **Pure Python Brandes** | None (stdlib) | 0 | ~3s for 5K nodes |
| NetworkX pure Python | NetworkX (~50 MB) | ~2 MB | ~1s for 5K nodes |
| NetworkX + graph-tool | NetworkX + C++ libs | ~100 MB | ~0.1s for 5K nodes |
| scipy.sparse.csgraph | SciPy (~200 MB) | ~10 MB | ~0.05s for 5K nodes |

### Decision

**Pure Python implementation** using only stdlib (`collections`, `math`, `heapq`).

Rationale: NeuralMind's house rule is "stdlib-only for core modules" (see `synapses.py`, `modularity.py`, `gaps.py`). NetworkX is 50 MB of dependencies for a ~3s computation that runs in a CLI command — not in the critical query path. This is a deliberate dep-size trade-off.

### Consequences

- **Positive:** Zero new dependencies. Matches house style. Auditable (80 lines of clear code).
- **Negative:** ~3x slower than NetworkX pure Python, ~30x slower than C.
- **Mitigation:** Acceptable because CLI latency budget is 10s, not ms.

---

## ADR-004: Inverse-Degree Gap Score vs Raw Betweenness

### Status: Accepted

### Context

Raw betweenness centrality flags hubs (utility files, shared types) as "gaps" because they naturally sit on many shortest paths. But these aren't missing — they're already well-connected.

Example: a `utils/logger.py` might have betweenness=0.3 (high) because everything imports it. But it's not a structural gap — it's a hub.

Options:

| Formula | Hubs penalized? | Bridges rewarded? | Formula complexity |
|---------|-----------------|-------------------|--------------------|
| **Betweenness × (1 / (degree + 1))** | ✅ Yes | ✅ Yes | Simple |
| Betweenness only | ❌ No | ✅ Yes | Trivial |
| Betweenness / degree | ✅ Yes | ⚠️ Div-by-zero risk | Simple |
| Community-spanning betweenness | ✅ Yes | ✅ Yes | Complex (community-aware paths) |

### Decision

Use **gap_score = betweenness × (1 / (degree + 1))**.

Rationale: Inverse-degree penalty naturally filters hubs without requiring a separate threshold. `degree + 1` avoids division by zero for isolated nodes. The formula is monotonic in betweenness and anti-monotonic in degree — exactly the ranking we want.

### Consequences

- **Positive:** Simple, interpretable, filters false positives (hubs), no div-by-zero.
- **Negative:** The +1 fudge factor is arbitrary; may need tuning with real-world data.
- **Mitigation:** Threshold τ is configurable (`--threshold` flag).

---

## ADR-005: Additive/Non-Destructive vs Integrated

### Status: Accepted

### Context

Two integration strategies:

| Strategy | Description | Risk | Benefit |
|----------|-------------|------|---------|
| **Additive (read-only)** | New module reads existing graph.json, no changes to build/query | Low — can't break existing flows | Fast to implement, safe, reversible |
| **Integrated** | Store betweenness in graph.json, use in L2/L3 query selection | High — changes query behavior, risk of regressions | Tighter coupling, "gap-aware" retrieval |

### Decision

**Additive (read-only)** for v1. G5 reads `graph.json`, computes gaps, reports them. Does not modify the graph or influence query behavior.

Rationale: InfraNodus gap detection is a separate surface from query/retrieval. Premature integration risks regressions in L0-L3 (the core value prop). Integration is a separate design question (G6 territory).

### Consequences

- **Positive:** Zero risk to existing functionality. Reversible. Fast to ship.
- **Negative:** Gaps aren't used to improve retrieval (yet).
- **Mitigation:** Future G6 can integrate if gap data proves valuable.

---

## ADR-006: Edge Weighting Scheme

### Status: Accepted: Accepted

### Context

Not all edges are equal. A `calls` relationship is structurally stronger than `contains`. The betweenness computation should weight edges accordingly.

Options:

| Scheme | Weights | Complexity |
|--------|---------|------------|
| **Type-based (chosen)** | calls=1.0, inherits=0.9, imports=0.8, contains=0.3, rationale=0.2 | Simple lookup |
| Uniform (unweighted) | All edges = 1.0 | Trivial |
| Confidence-based | Use `confidence_score` from G1 dynamic import resolution | Complex, data not always available |
| Frequency-based | Count edge occurrences in source | Requires source scan |

### Decision

**Type-based weighting** with the schema:

| Edge Type | Weight | Rationale |
|-----------|--------|-----------|
| `calls` | 1.0 | Strongest structural link — function A invokes function B |
| `inherits` | 0.9 | Strong OOP link — class A extends class B |
| `imports_from` | 0.8 | Dependency — module A requires module B |
| `contains` | 0.3 | Structural containment (file contains function) |
| `rationale_for` | 0.2 | Docstring-derived link (weakest) |

Rationale: Matches the semantic weight of each relationship. `calls` edges are the "wires" of the program — shortest paths along call edges represent real execution flow.

### Consequences

- **Positive:** Reflects real structural importance. Deterministic.
- **Negative:** Weights are hand-tuned, not learned.
- **Mitigation:** Weights are easy to adjust if real-world data shows misrankings.

---

*Generated by Hermes. G5-ADR — v1.0. Claim tier: B+.*
